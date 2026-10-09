from __future__ import annotations
import os
import logging
from typing import Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from models.schemas import Panelist, PanelSelectionOutput, EvidenceDossier
from models.prompts import PANEL_ARCHITECT_SYSTEM_PROMPT
from services.evidence import EvidenceService

logger = logging.getLogger(__name__)

def get_chat_model(temperature: float = 0.5):
    """Retrieve configured ChatOpenAI model."""
    model_name = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    kwargs = {"model": model_name, "temperature": temperature, "api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)

class PanelArchitect:
    """Architect agent that dynamically selects a 4-6 member panel from evidence."""

    @staticmethod
    def construct_panel(
        topic: str,
        dossier: EvidenceDossier,
        domain_hint: Optional[str] = None
    ) -> PanelSelectionOutput:
        """Select a diverse, grounded panel of debaters."""
        evidence_text = EvidenceService.format_sources_for_context(dossier.sources)
        disputes_text = "\n".join(f"- {d}" for d in dossier.core_disputes)

        prompt = ChatPromptTemplate.from_messages([
            ("system", PANEL_ARCHITECT_SYSTEM_PROMPT),
            ("user", 
             "Topic: {topic}\n"
             "Domain Hint: {domain_hint}\n"
             "Core Disputes:\n{disputes_text}\n\n"
             "Evidence Dossier:\n{evidence_text}\n\n"
             "Select a 4-6 member debate panel. MANDATORY: Include a Public Representative.")
        ])

        try:
            llm = get_chat_model(temperature=0.3)
            structured_llm = llm.with_structured_output(PanelSelectionOutput)
            chain = prompt | structured_llm
            output: PanelSelectionOutput = chain.invoke({
                "topic": topic,
                "domain_hint": domain_hint or "General Current Affairs",
                "disputes_text": disputes_text,
                "evidence_text": evidence_text
            })
        except Exception as e:
            logger.error(f"Panel Architect LLM call failed: {e}. Fallback to rule-based panel.")
            output = PanelArchitect._fallback_panel(topic, dossier)

        # Enforce non-negotiable invariant: Public Representative MUST be included
        output = PanelArchitect.enforce_public_representation(output, topic, dossier)
        return output

    @staticmethod
    def enforce_public_representation(
        panel_output: PanelSelectionOutput,
        topic: str,
        dossier: EvidenceDossier
    ) -> PanelSelectionOutput:
        """Guarantee that the Public role is present."""
        has_public = any(
            p.identity_type == "public_representative" or "public" in p.id.lower() or "citizen" in p.role.lower()
            for p in panel_output.participants
        )

        if not has_public:
            public_panelist = Panelist(
                id="public_rep",
                display_name="Citizen Representative (Civil Society)",
                role="Representative of Affected Citizens & Everyday Consumers",
                identity_type="public_representative",
                selection_reason="Mandatory Public Voice: Represents the direct socio-economic, privacy, and everyday impacts of this issue.",
                documented_position="Demands transparency, accountability, and fairness for the general populace rather than institutional interests alone.",
                interests=["Everyday affordability", "Consumer safety", "Democratic accountability", "Equitable impact"],
                relevant_source_ids=[s.id for s in dossier.sources[:2]]
            )
            # Cap at 6 panelists max
            if len(panel_output.participants) >= 6:
                panel_output.participants[-1] = public_panelist
            else:
                panel_output.participants.append(public_panelist)

        return panel_output

    @staticmethod
    def _fallback_panel(topic: str, dossier: EvidenceDossier) -> PanelSelectionOutput:
        """Deterministic fallback panel in case of API outages."""
        src_ids = [s.id for s in dossier.sources[:2]]
        return PanelSelectionOutput(
            participants=[
                Panelist(
                    id="policy_analyst",
                    display_name="Dr. Marcus Vance",
                    role="Senior Regulatory Policy Analyst",
                    identity_type="expert",
                    selection_reason="Analyzes the legal and systemic compliance implications.",
                    documented_position="Focuses on institutional compliance and structured governance frameworks.",
                    interests=["Institutional integrity", "Regulatory compliance"],
                    relevant_source_ids=src_ids
                ),
                Panelist(
                    id="industry_advocate",
                    display_name="Elena Chen",
                    role="Industry Innovation Spokesperson",
                    identity_type="institution",
                    selection_reason="Represents commercial viability and technological competitiveness.",
                    documented_position="Advocates for market flexibility and minimal administrative friction.",
                    interests=["Technological progress", "Market agility"],
                    relevant_source_ids=src_ids
                ),
                Panelist(
                    id="public_rep",
                    display_name="Sarah Jenkins (Public Voice)",
                    role="Civil Society & Citizen Representative",
                    identity_type="public_representative",
                    selection_reason="Essential proxy for everyday consumers and grassroots stakeholders.",
                    documented_position="Focuses on public wellbeing, transparency, and consumer protection.",
                    interests=["Public welfare", "Accountability", "Affordability"],
                    relevant_source_ids=src_ids
                ),
                Panelist(
                    id="independent_researcher",
                    display_name="Prof. Tariq Al-Mansoor",
                    role="Independent Domain Researcher",
                    identity_type="expert",
                    selection_reason="Provides empirical grounding and evidence assessment.",
                    documented_position="Relies strictly on empirical data and historical precedents.",
                    interests=["Evidence rigor", "Long-term outcomes"],
                    relevant_source_ids=src_ids
                )
            ],
            missing_perspectives_note="Fallback panel synthesized due to temporary service unavailability."
        )
