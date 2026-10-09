from __future__ import annotations
import os
import json
import sqlite3
import datetime
from typing import List, Dict, Any, Optional
from models.schemas import DebateMessage, ClaimRecord, InfluenceEdge, FinalReport, Source, Panelist

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "sessions.db")

class PersistenceService:
    """SQLite persistence service for saving and loading completed NarrativeLab debate sessions."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create necessary tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    domain_hint TEXT,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    dossier_json TEXT,
                    panel_json TEXT,
                    final_report_json TEXT
                )
            """)

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    round INTEGER NOT NULL,
                    speaker_id TEXT NOT NULL,
                    speaker_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    cited_source_ids TEXT,
                    target_claim_ids TEXT,
                    explicit_concessions TEXT,
                    position_shift TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                )
            """)

            # Claims ledger table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    speaker_id TEXT NOT NULL,
                    claim_text TEXT NOT NULL,
                    source_ids TEXT,
                    status TEXT NOT NULL,
                    round_introduced INTEGER NOT NULL,
                    message_id TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                )
            """)

            # Influence edges table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS influence_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    source_node TEXT NOT NULL,
                    target_node TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    justifying_message_ids TEXT,
                    evidence_ids TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                )
            """)
            conn.commit()

    def save_session(
        self,
        session_id: str,
        topic: str,
        domain_hint: Optional[str],
        sources: List[Source],
        panel: List[Panelist],
        messages: List[DebateMessage],
        claims: Dict[str, ClaimRecord],
        edges: List[InfluenceEdge],
        final_report: Optional[FinalReport] = None,
        status: str = "completed"
    ):
        """Save a complete debate session to SQLite."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            dossier_json = json.dumps([s.model_dump() for s in sources])
            panel_json = json.dumps([p.model_dump() for p in panel])
            report_json = json.dumps(final_report.model_dump()) if final_report else None

            cursor.execute("""
                INSERT OR REPLACE INTO sessions 
                (session_id, topic, domain_hint, created_at, status, dossier_json, panel_json, final_report_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, topic, domain_hint, now_iso, status, dossier_json, panel_json, report_json))

            # Insert messages
            for msg in messages:
                cursor.execute("""
                    INSERT INTO messages 
                    (session_id, message_id, round, speaker_id, speaker_name, content, cited_source_ids, target_claim_ids, explicit_concessions, position_shift)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, msg.id, msg.round, msg.speaker_id, msg.speaker_name, msg.content,
                    json.dumps(msg.cited_source_ids),
                    json.dumps(msg.target_claim_ids),
                    json.dumps(msg.explicit_concessions),
                    msg.position_shift
                ))

            # Insert claims
            for cid, clm in claims.items():
                cursor.execute("""
                    INSERT INTO claims
                    (session_id, claim_id, speaker_id, claim_text, source_ids, status, round_introduced, message_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, clm.id, clm.speaker_id, clm.claim_text,
                    json.dumps(clm.source_ids),
                    clm.status,
                    clm.round_introduced,
                    clm.message_id
                ))

            # Insert edges
            for edge in edges:
                cursor.execute("""
                    INSERT INTO influence_edges
                    (session_id, source_node, target_node, edge_type, justifying_message_ids, evidence_ids)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session_id, edge.source_node, edge.target_node, edge.edge_type,
                    json.dumps(edge.justifying_message_ids),
                    json.dumps(edge.evidence_ids)
                ))

            conn.commit()

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List summary of saved debate sessions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, topic, domain_hint, created_at, status FROM sessions ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load full session details by session_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            session_row = cursor.fetchone()
            if not session_row:
                return None

            cursor.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
            messages = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM claims WHERE session_id = ?", (session_id,))
            claims = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM influence_edges WHERE session_id = ?", (session_id,))
            edges = [dict(r) for r in cursor.fetchall()]

            return {
                "session": dict(session_row),
                "messages": messages,
                "claims": claims,
                "edges": edges
            }
