from __future__ import annotations
import pytest
from models.schemas import Panelist, PanelSelectionOutput, EvidenceDossier, Source
from agents.panel_architect import PanelArchitect

def test_enforce_public_representation_when_absent():
    """Verify that a Public representative is strictly injected if omitted by the model."""
    dossier = EvidenceDossier(
        topic_summary="Autonomous weapons regulation",
        timeline=[],
        core_disputes=[],
        sources=[Source(id="SRC_01", url="https://example.com", title="Sample", snippet="Context")]
    )

    # Panel without a public voice
    initial_panel = PanelSelectionOutput(
        participants=[
            Panelist(
                id="military_rep",
                display_name="Gen. Vance",
                role="Defense Strategist",
                identity_type="institution",
                selection_reason="Strategic perspective",
                documented_position="Deterrence capability",
                interests=["Defense superiority"],
                relevant_source_ids=["SRC_01"]
            ),
            Panelist(
                id="tech_exec",
                display_name="Tech CEO",
                role="Defense Contractor",
                identity_type="institution",
                selection_reason="Commercial readiness",
                documented_position="Rapid deployment",
                interests=["Market expansion"],
                relevant_source_ids=["SRC_01"]
            )
        ]
    )

    validated = PanelArchitect.enforce_public_representation(initial_panel, "Autonomous weapons", dossier)
    
    # Must now include a public representative
    has_public = any(
        p.identity_type == "public_representative" or "public" in p.id.lower()
        for p in validated.participants
    )
    assert has_public is True, "Public Representative must always be present in the panel"

def test_panel_size_bounds():
    """Verify panel stays within 4-6 members."""
    dossier = EvidenceDossier(
        topic_summary="Sample",
        timeline=[],
        core_disputes=[],
        sources=[]
    )
    fallback = PanelArchitect._fallback_panel("Sample Topic", dossier)
    assert 4 <= len(fallback.participants) <= 6
