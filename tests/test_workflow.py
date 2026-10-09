from __future__ import annotations
import pytest
from graph.workflow import build_debate_graph
from graph.state import DebateState
from models.schemas import Source, EvidenceDossier, Panelist

def test_workflow_compilation():
    """Verify that the StateGraph compiles cleanly with all nodes and conditional edges."""
    graph = build_debate_graph()
    assert graph is not None

def test_graph_structure():
    """Verify presence of key nodes in graph."""
    graph = build_debate_graph()
    node_names = graph.nodes.keys()
    for expected in [
        "research_topic",
        "build_evidence_dossier",
        "select_panel",
        "validate_panel",
        "opening_positions",
        "select_next_speaker",
        "generate_reaction",
        "update_debate_state",
        "observer_analysis",
        "final_report"
    ]:
        assert expected in node_names, f"Node {expected} missing from graph"
