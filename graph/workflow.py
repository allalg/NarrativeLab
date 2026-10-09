from __future__ import annotations
import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from graph.state import DebateState
from graph.nodes import (
    research_topic_node,
    build_evidence_dossier_node,
    select_panel_node,
    validate_panel_node,
    opening_positions_node,
    select_next_speaker_node,
    generate_reaction_node,
    update_debate_state_node,
    observer_analysis_node,
    final_report_node,
)

logger = logging.getLogger(__name__)

def should_continue(state: DebateState) -> Literal["select_next_speaker", "final_report"]:
    """Conditional router: loop turns until max_rounds (3) is exceeded."""
    current_round = state.get("current_round", 1)
    max_rounds = state.get("max_rounds", 3)
    
    if current_round > max_rounds:
        logger.info(f"Max rounds ({max_rounds}) reached. Routing to final report.")
        return "final_report"
    return "select_next_speaker"

def build_debate_graph() -> StateGraph:
    """Construct and compile the NarrativeLab debate orchestrator graph."""
    builder = StateGraph(DebateState)

    # Add Nodes
    builder.add_node("research_topic", research_topic_node)
    builder.add_node("build_evidence_dossier", build_evidence_dossier_node)
    builder.add_node("select_panel", select_panel_node)
    builder.add_node("validate_panel", validate_panel_node)
    builder.add_node("opening_positions", opening_positions_node)
    builder.add_node("select_next_speaker", select_next_speaker_node)
    builder.add_node("generate_reaction", generate_reaction_node)
    builder.add_node("update_debate_state", update_debate_state_node)
    builder.add_node("observer_analysis", observer_analysis_node)
    builder.add_node("final_report", final_report_node)

    # Set Entry Point
    builder.set_entry_point("research_topic")

    # Connect Edges
    builder.add_edge("research_topic", "build_evidence_dossier")
    builder.add_edge("build_evidence_dossier", "select_panel")
    builder.add_edge("select_panel", "validate_panel")
    builder.add_edge("validate_panel", "opening_positions")
    builder.add_edge("opening_positions", "select_next_speaker")
    builder.add_edge("select_next_speaker", "generate_reaction")
    builder.add_edge("generate_reaction", "update_debate_state")
    builder.add_edge("update_debate_state", "observer_analysis")

    # Conditional Branching Edge
    builder.add_conditional_edges(
        "observer_analysis",
        should_continue,
        {
            "select_next_speaker": "select_next_speaker",
            "final_report": "final_report"
        }
    )

    # Terminal Edge
    builder.add_edge("final_report", END)

    return builder.compile()
