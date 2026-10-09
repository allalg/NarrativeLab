from __future__ import annotations
import os
import uuid
import logging
from typing import List, Dict, Optional, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from models.schemas import Panelist, EvidenceDossier, DebateMessage, ClaimRecord
from models.prompts import DEBATE_AGENT_SYSTEM_PROMPT
from services.evidence import EvidenceService

logger = logging.getLogger(__name__)

def get_chat_model(temperature: float = 0.7):
    """Retrieve configured ChatOpenAI model."""
    model_name = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    kwargs = {"model": model_name, "temperature": temperature, "api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)

class DebateAgent:
    """Agent representing a single debating participant with strict reactive rules."""

    @staticmethod
    def generate_turn(
        speaker: Panelist,
        topic: str,
        dossier: EvidenceDossier,
        recent_messages: List[DebateMessage],
        claims: Dict[str, ClaimRecord],
        current_round: int,
        turn_index: int,
        is_opening: bool = False
    ) -> DebateMessage:
        """Generate a simulated reactive debate response grounded in evidence."""
        evidence_context = EvidenceService.format_sources_for_context(dossier.sources)
        message_id = f"MSG_R{current_round}_{turn_index:02d}"

        # Format recent conversation history
        history_lines = []
        for m in recent_messages[-4:]:
            citations = f" [Cited: {', '.join(m.cited_source_ids)}]" if m.cited_source_ids else ""
            targets = f" [Targets: {', '.join(m.target_claim_ids)}]" if m.target_claim_ids else ""
            history_lines.append(f"{m.speaker_name} ({m.id}){citations}{targets}:\n\"{m.content}\"\n")
        history_text = "\n".join(history_lines) if history_lines else "None yet (Opening Round)."

        # Format active claims ledger
        claims_lines = []
        for cid, c in list(claims.items())[-6:]:
            claims_lines.append(f"- [{c.id}] ({c.status}) by {c.speaker_id}: \"{c.claim_text}\" (Sources: {', '.join(c.source_ids)})")
        claims_text = "\n".join(claims_lines) if claims_lines else "No claims logged yet."

        if is_opening:
            turn_instructions = (
                "This is ROUND 1: OPENING STATEMENTS.\n"
                "State your initial position clearly, grounding your arguments in the Evidence Dossier.\n"
                "Cite relevant Source IDs (e.g. SRC_01) for factual assertions.\n"
                "Keep your response concise, sharp, and focused on your core interests."
            )
        else:
            turn_instructions = (
                f"This is ROUND {current_round}: REACTIVE DEBATE.\n"
                "MANDATORY: You MUST directly engage with at least one prior claim or statement above.\n"
                "Identify which claim ID you are challenging or supporting in `target_claim_ids`.\n"
                "Cite relevant Source IDs (e.g. SRC_02) for factual assertions.\n"
                "If an opponent made a persuasive, evidenced counterargument, acknowledge it in `explicit_concessions`.\n"
                "Do NOT repeat your opening statement; push the dialogue forward."
            )

        system_prompt = DEBATE_AGENT_SYSTEM_PROMPT.format(
            display_name=speaker.display_name,
            role=speaker.role,
            topic=topic,
            identity_type=speaker.identity_type,
            documented_position=speaker.documented_position,
            interests=", ".join(speaker.interests),
            evidence_context=evidence_context
        )

        user_prompt = (
            f"=== CONVERSATION TRANSCRIPT SO FAR ===\n{history_text}\n\n"
            f"=== ACTIVE CLAIMS LEDGER ===\n{claims_text}\n\n"
            f"=== INSTRUCTIONS FOR YOUR TURN ===\n{turn_instructions}"
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])

        try:
            llm = get_chat_model(temperature=0.6)
            structured_llm = llm.with_structured_output(DebateMessage)
            chain = prompt | structured_llm
            result: DebateMessage = chain.invoke({})
            
            # Ensure stable metadata
            result.id = message_id
            result.round = current_round
            result.speaker_id = speaker.id
            result.speaker_name = speaker.display_name
            
            # Clean citations to only include valid dossier sources
            valid_srcs = {s.id for s in dossier.sources}
            result.cited_source_ids = [s for s in result.cited_source_ids if s in valid_srcs]
            
            return result
        except Exception as e:
            logger.error(f"DebateAgent turn generation failed for {speaker.id}: {e}. Using fallback turn.")
            return DebateAgent._fallback_turn(
                speaker=speaker,
                current_round=current_round,
                turn_index=turn_index,
                is_opening=is_opening,
                dossier=dossier
            )

    @staticmethod
    def _fallback_turn(
        speaker: Panelist,
        current_round: int,
        turn_index: int,
        is_opening: bool,
        dossier: EvidenceDossier
    ) -> DebateMessage:
        """Deterministic fallback message to ensure continuity during service disruptions."""
        first_src = dossier.sources[0].id if dossier.sources else "SRC_01"
        if is_opening:
            content = (
                f"From the perspective of {speaker.role}, we must approach this issue by prioritizing "
                f"{', '.join(speaker.interests)}. Based on preliminary reporting ({first_src}), "
                f"our documented stance is that {speaker.documented_position}."
            )
        else:
            content = (
                f"I must directly address the assertions raised earlier. As {speaker.role}, "
                f"we insist that any viable resolution must account for {speaker.interests[0]}. "
                f"The available evidence ({first_src}) underscores our concern."
            )

        return DebateMessage(
            id=f"MSG_R{current_round}_{turn_index:02d}",
            round=current_round,
            speaker_id=speaker.id,
            speaker_name=speaker.display_name,
            content=content,
            cited_source_ids=[first_src] if dossier.sources else [],
            target_claim_ids=[],
            explicit_concessions=[],
            position_shift=None,
            unresolved_questions=[]
        )
