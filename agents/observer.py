from __future__ import annotations
import os
import logging
from typing import List, Dict, Optional, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from models.schemas import (
    Panelist,
    EvidenceDossier,
    DebateMessage,
    ClaimRecord,
    PositionSnapshot,
    InfluenceEdge,
    ObserverRoundUpdate,
    FinalReport,
)
from models.prompts import OBSERVER_ROUND_SYSTEM_PROMPT, FINAL_REPORT_SYSTEM_PROMPT
from services.evidence import EvidenceService

logger = logging.getLogger(__name__)

def get_chat_model(temperature: float = 0.2):
    """Retrieve low-temperature model for objective observer analysis."""
    model_name = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    kwargs = {"model": model_name, "temperature": temperature, "api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)

class ObserverEngine:
    """Independent Observer that extracts claims, tracks positions, and charts influence."""

    @staticmethod
    def analyze_round(
        round_num: int,
        round_messages: List[DebateMessage],
        panel: List[Panelist],
        existing_claims: Dict[str, ClaimRecord],
        dossier: EvidenceDossier
    ) -> ObserverRoundUpdate:
        """Run round-level analytical extraction."""
        evidence_context = EvidenceService.format_sources_for_context(dossier.sources)

        # Format messages for observer inspection
        transcript_lines = []
        for m in round_messages:
            transcript_lines.append(
                f"[{m.id}] {m.speaker_name} ({m.speaker_id}):\n"
                f"Content: \"{m.content}\"\n"
                f"Cited Sources: {', '.join(m.cited_source_ids) or 'None'}\n"
                f"Targeted Claims: {', '.join(m.target_claim_ids) or 'None'}\n"
                f"Explicit Concessions: {', '.join(m.explicit_concessions) or 'None'}\n"
                f"Position Shift: {m.position_shift or 'None'}\n"
            )
        transcript_text = "\n".join(transcript_lines)

        claims_lines = [f"[{c.id}] ({c.status}) by {c.speaker_id}: \"{c.claim_text}\"" for c in existing_claims.values()]
        existing_claims_text = "\n".join(claims_lines) if claims_lines else "None."

        prompt = ChatPromptTemplate.from_messages([
            ("system", OBSERVER_ROUND_SYSTEM_PROMPT),
            ("user",
             f"=== ROUND {round_num} TRANSCRIPT ===\n{transcript_text}\n\n"
             f"=== EXISTING CLAIM LEDGER ===\n{existing_claims_text}\n\n"
             f"=== EVIDENCE DOSSIER ===\n{evidence_context}\n\n"
             f"Analyze Round {round_num}. Extract new claims, update existing claim statuses, "
             f"create position snapshots for all debaters, identify typed influence edges with justifying message IDs, "
             f"and note unsupported assertions or narrative shifts.")
        ])

        try:
            llm = get_chat_model(temperature=0.2)
            structured_llm = llm.with_structured_output(ObserverRoundUpdate)
            chain = prompt | structured_llm
            update: ObserverRoundUpdate = chain.invoke({})
            update.round = round_num
            
            # Post-process: ensure claim citations strictly exist in dossier
            valid_srcs = {s.id for s in dossier.sources}
            for clm in update.new_claims:
                clm.source_ids = [s for s in clm.source_ids if s in valid_srcs]
                if not clm.source_ids:
                    clm.status = "unverified"
                    
            return update
        except Exception as e:
            logger.error(f"Observer round analysis failed for round {round_num}: {e}. Building deterministic update.")
            return ObserverEngine._fallback_round_update(round_num, round_messages, panel)

    @staticmethod
    def generate_final_report(
        topic: str,
        panel: List[Panelist],
        messages: List[DebateMessage],
        claims: Dict[str, ClaimRecord],
        updates: List[ObserverRoundUpdate],
        dossier: EvidenceDossier
    ) -> FinalReport:
        """Synthesize final objective report across the entire debate."""
        evidence_context = EvidenceService.format_sources_for_context(dossier.sources)

        # Summarize key stats
        total_messages = len(messages)
        total_claims = len(claims)
        supported_claims = [c.claim_text for c in claims.values() if c.status == "supported"]
        disputed_claims = [c.claim_text for c in claims.values() if c.status in ("disputed", "contradicted")]

        user_content = (
            f"Topic: {topic}\n"
            f"Panelists: {', '.join(p.display_name for p in panel)}\n"
            f"Total Messages: {total_messages} | Total Claims: {total_claims}\n"
            f"Supported Claims: {supported_claims[:5]}\n"
            f"Disputed Claims: {disputed_claims[:5]}\n\n"
            f"Evidence Dossier Summary:\n{evidence_context}\n\n"
            "Produce the comprehensive Final Report strictly grounded in this evidence."
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", FINAL_REPORT_SYSTEM_PROMPT.format(topic=topic)),
            ("user", user_content)
        ])

        try:
            llm = get_chat_model(temperature=0.2)
            structured_llm = llm.with_structured_output(FinalReport)
            chain = prompt | structured_llm
            report: FinalReport = chain.invoke({})
            report.topic = topic
            return report
        except Exception as e:
            logger.error(f"Final Report generation failed: {e}. Building deterministic report.")
            return ObserverEngine._fallback_final_report(topic, panel, claims, dossier)

    @staticmethod
    def _fallback_round_update(
        round_num: int,
        messages: List[DebateMessage],
        panel: List[Panelist]
    ) -> ObserverRoundUpdate:
        """Rule-based fallback for round update."""
        new_claims = []
        new_edges = []
        snapshots = []

        for idx, m in enumerate(messages, start=1):
            claim_id = f"CLM_R{round_num}_{idx:02d}"
            new_claims.append(
                ClaimRecord(
                    id=claim_id,
                    speaker_id=m.speaker_id,
                    claim_text=f"Core assertion made by {m.speaker_name} in {m.id}",
                    source_ids=m.cited_source_ids,
                    status="supported" if m.cited_source_ids else "unverified",
                    round_introduced=round_num,
                    message_id=m.id
                )
            )
            for src in m.cited_source_ids:
                new_edges.append(
                    InfluenceEdge(
                        source_node=m.speaker_id,
                        target_node=src,
                        edge_type="cited",
                        justifying_message_ids=[m.id],
                        evidence_ids=[src]
                    )
                )

        for p in panel:
            snapshots.append(
                PositionSnapshot(
                    speaker_id=p.id,
                    round=round_num,
                    stated_position=p.documented_position,
                    confidence_level="firm",
                    rationale="Baseline documented stance"
                )
            )

        return ObserverRoundUpdate(
            round=round_num,
            new_claims=new_claims,
            updated_claims=[],
            position_snapshots=snapshots,
            new_influence_edges=new_edges,
            narrative_shifts=[f"Round {round_num} introduced substantive stakeholder claims."],
            unsupported_assertions=[],
            unresolved_questions=["Empirical verification of claimed trade-offs."]
        )

    @staticmethod
    def _fallback_final_report(
        topic: str,
        panel: List[Panelist],
        claims: Dict[str, ClaimRecord],
        dossier: EvidenceDossier
    ) -> FinalReport:
        """Rule-based fallback final report."""
        return FinalReport(
            topic=topic,
            established_facts=[
                f"The debate engaged {len(panel)} key perspectives on '{topic}'.",
                "A shared evidence dossier was provided to ground claims."
            ],
            disputed_interpretations=[
                "Conflicting priorities between regulatory oversight and technological/market flexibility.",
                "Differing valuations of public consumer protections versus administrative burdens."
            ],
            unresolved_questions=[
                "How the economic burden of compliance is distributed.",
                "Long-term empirical outcomes over subsequent quarters."
            ],
            evidence_gaps=[
                "Independent multi-jurisdictional empirical studies are limited."
            ],
            narrative_evolution_summary=(
                f"The 3-round simulation for '{topic}' transitioned from initial opening stances "
                f"into direct clashes regarding empirical evidence and societal impacts."
            )
        )
