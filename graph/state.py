from __future__ import annotations
from typing import TypedDict, List, Dict, Optional, Annotated
import operator
from models.schemas import (
    Source,
    EvidenceDossier,
    Panelist,
    DebateMessage,
    ClaimRecord,
    PositionSnapshot,
    InfluenceEdge,
    ObserverRoundUpdate,
    FinalReport,
)

class DebateState(TypedDict):
    """Global state container for the NarrativeLab LangGraph workflow."""
    
    # Topic specification
    session_id: str
    topic: str
    domain_hint: Optional[str]
    
    # Research and Evidence
    research_dossier: Optional[EvidenceDossier]
    sources: List[Source]
    
    # Panel
    panel: List[Panelist]
    panel_validation_attempts: int
    
    # Dialogue & Progress
    current_round: int
    max_rounds: int
    messages: List[DebateMessage]
    claims: Dict[str, ClaimRecord] # claim_id -> ClaimRecord
    position_snapshots: List[PositionSnapshot]
    influence_edges: List[InfluenceEdge]
    
    # Speaker dispatching & turn routing
    next_speaker_id: Optional[str]
    current_speaker_turns_this_round: Dict[str, int]
    unanswered_challenges: List[str] # claim_ids requiring response
    
    # Observer & Analytics
    observer_updates: List[ObserverRoundUpdate]
    final_report: Optional[FinalReport]
    
    # Runtime errors and diagnostics
    errors: List[str]
