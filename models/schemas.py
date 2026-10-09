from __future__ import annotations
from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field

# -------------------------------------------------------------
# 1. Evidence Models
# -------------------------------------------------------------
class Source(BaseModel):
    id: str = Field(description="Unique source ID, e.g. SRC_01")
    url: str = Field(description="Canonical URL of the source")
    title: str = Field(description="Headline or title of the source")
    publisher: Optional[str] = Field(default=None, description="Publishing organization or outlet")
    published_date: Optional[str] = Field(default=None, description="Publication date or timeframe")
    snippet: str = Field(description="Key excerpt or summary from the source")

class EvidenceDossier(BaseModel):
    topic_summary: str = Field(description="Concise overview of the topic and context")
    timeline: List[str] = Field(default_factory=list, description="Chronological key events")
    core_disputes: List[str] = Field(default_factory=list, description="Key points of contention")
    sources: List[Source] = Field(default_factory=list, description="Normalized source records")

# -------------------------------------------------------------
# 2. Panelist Models
# -------------------------------------------------------------
class Panelist(BaseModel):
    id: str = Field(description="Unique slug identifier, e.g. 'dr_elena' or 'public'")
    display_name: str = Field(description="Full display name, e.g. 'Dr. Elena Rostova'")
    role: str = Field(description="Specific role, e.g. 'AI Safety Researcher' or 'Citizen Representative'")
    identity_type: Literal["public_figure", "institution", "expert", "affected_community", "public_representative"] = Field(
        description="Category of the participant"
    )
    selection_reason: str = Field(description="Why this perspective is essential based on evidence")
    documented_position: str = Field(description="Established or documented perspective on the issue")
    interests: List[str] = Field(default_factory=list, description="Core priorities and concerns")
    relevant_source_ids: List[str] = Field(default_factory=list, description="Referenced source IDs")

class PanelSelectionOutput(BaseModel):
    participants: List[Panelist] = Field(description="List of 4 to 6 selected debaters including the Public")
    missing_perspectives_note: Optional[str] = Field(
        default=None, 
        description="Noteworthy viewpoints omitted due to lack of evidence"
    )

# -------------------------------------------------------------
# 3. Claims & Dialogue Models
# -------------------------------------------------------------
class ClaimRecord(BaseModel):
    id: str = Field(description="Unique claim ID, e.g. CLM_101")
    speaker_id: str = Field(description="ID of the speaker who made the claim")
    claim_text: str = Field(description="Exact substantive assertion")
    source_ids: List[str] = Field(default_factory=list, description="Source IDs cited to support the claim")
    status: Literal["supported", "contradicted", "disputed", "unverified", "unresolved"] = Field(
        default="unverified",
        description="Current evidentiary status of the claim"
    )
    challenged_by_claim_ids: List[str] = Field(default_factory=list, description="Claims challenging this claim")
    round_introduced: int = Field(description="Round number when introduced")
    message_id: str = Field(description="Originating message ID")

class DebateMessage(BaseModel):
    id: str = Field(description="Unique message ID, e.g. MSG_R1_01")
    round: int = Field(description="Round index (1 to 3)")
    speaker_id: str = Field(description="ID of speaking participant")
    speaker_name: str = Field(description="Display name of speaking participant")
    content: str = Field(description="Spoken dialogue text")
    cited_source_ids: List[str] = Field(default_factory=list, description="Source IDs referenced in content")
    target_claim_ids: List[str] = Field(default_factory=list, description="Prior claim IDs directly addressed or challenged")
    explicit_concessions: List[str] = Field(default_factory=list, description="Explicit points conceded to other debaters")
    position_shift: Optional[str] = Field(default=None, description="Explicit shift in stance, if any occurred")
    unresolved_questions: List[str] = Field(default_factory=list, description="Open questions raised")

# -------------------------------------------------------------
# 4. Observer & Influence Models
# -------------------------------------------------------------
class InfluenceEdge(BaseModel):
    source_node: str = Field(description="Initiating agent ID or claim ID")
    target_node: str = Field(description="Targeted agent ID or claim ID")
    edge_type: Literal["challenged", "supported", "cited", "responded_to", "conceded", "revised_after"] = Field(
        description="Type of relational influence"
    )
    justifying_message_ids: List[str] = Field(description="Message IDs that directly demonstrate this edge")
    evidence_ids: List[str] = Field(default_factory=list, description="Evidence IDs involved")

class PositionSnapshot(BaseModel):
    speaker_id: str = Field(description="ID of the participant")
    round: int = Field(description="Round number")
    stated_position: str = Field(description="Summary of current stance")
    confidence_level: Literal["firm", "exploring", "conceding", "shifting"] = Field(
        description="Expressed confidence"
    )
    rationale: str = Field(description="Justification stated by the debater")

class ObserverRoundUpdate(BaseModel):
    round: int = Field(description="Debate round analyzed")
    new_claims: List[ClaimRecord] = Field(default_factory=list, description="Claims made in this round")
    updated_claims: List[ClaimRecord] = Field(default_factory=list, description="Claims whose status changed")
    position_snapshots: List[PositionSnapshot] = Field(default_factory=list, description="Snapshot of each speaker's stance")
    new_influence_edges: List[InfluenceEdge] = Field(default_factory=list, description="Influence links created this round")
    narrative_shifts: List[str] = Field(default_factory=list, description="Observed framing evolutions")
    unsupported_assertions: List[str] = Field(default_factory=list, description="Assertions made without cited evidence")
    unresolved_questions: List[str] = Field(default_factory=list, description="Critical unanswered points")

class FinalReport(BaseModel):
    topic: str = Field(description="Topic investigated")
    established_facts: List[str] = Field(description="Key claims supported by consensus or evidence")
    disputed_interpretations: List[str] = Field(description="Central unresolved disagreements")
    unresolved_questions: List[str] = Field(description="Open questions for future investigation")
    evidence_gaps: List[str] = Field(description="Areas where reliable sources were lacking")
    narrative_evolution_summary: str = Field(description="Synthesis of how arguments and positions evolved across rounds")
