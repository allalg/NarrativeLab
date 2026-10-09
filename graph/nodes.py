from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Optional
from graph.state import DebateState
from models.schemas import (
    Source,
    EvidenceDossier,
    Panelist,
    DebateMessage,
    ClaimRecord,
    PositionSnapshot,
    InfluenceEdge,
    FinalReport,
)
from services.search import SearchService
from services.evidence import EvidenceService
from services.persistence import PersistenceService
from agents.panel_architect import PanelArchitect
from agents.debate_agent import DebateAgent
from agents.observer import ObserverEngine

logger = logging.getLogger(__name__)

# Singletons for services
_search_service = SearchService()
_persistence_service = PersistenceService()

def research_topic_node(state: DebateState) -> Dict[str, Any]:
    """Node: Search web for sources on the topic using credit-efficient hybrid search."""
    topic = state["topic"]
    logger.info(f"Researching topic: {topic}")
    
    # Primary search query (uses Tavily basic if key present, else DDG)
    primary_sources = _search_service.search(
        query=f"{topic} current news analysis controversy",
        provider="hybrid",
        max_results=5,
        is_primary_topic_query=True
    )
    
    # Secondary search query (uses free DuckDuckGo to preserve user credits)
    secondary_sources = _search_service.search(
        query=f"{topic} key stakeholders debate perspectives",
        provider="duckduckgo",
        max_results=5,
        is_primary_topic_query=False
    )
    
    all_raw_sources = primary_sources + secondary_sources
    deduped = EvidenceService.deduplicate_sources(all_raw_sources)
    
    return {"sources": deduped}

def build_evidence_dossier_node(state: DebateState) -> Dict[str, Any]:
    """Node: Synthesize sources into an EvidenceDossier with core disputes."""
    sources = state.get("sources", [])
    topic = state["topic"]
    
    # If no sources were retrieved, create a baseline source
    if not sources:
        sources = [
            Source(
                id="SRC_01",
                url="https://en.wikipedia.org/wiki/" + topic.replace(" ", "_"),
                title=f"Background Briefing on {topic}",
                snippet=f"General domain context and documented public viewpoints regarding {topic}."
            )
        ]
        
    core_disputes = [
        f"Differing stakeholder priorities regarding {topic}",
        "Empirical trade-offs between speed, safety, and regulation",
        "Public welfare vs. institutional and commercial compliance costs"
    ]
    
    dossier = EvidenceDossier(
        topic_summary=f"Curated evidence dossier analyzing recent reporting and disputes around: {topic}.",
        timeline=[
            "Recent developments reported in current coverage",
            "Regulatory or institutional stakeholder public statements",
            "Current debate and competing policy proposals"
        ],
        core_disputes=core_disputes,
        sources=sources
    )
    
    return {"research_dossier": dossier, "sources": sources}

def select_panel_node(state: DebateState) -> Dict[str, Any]:
    """Node: Dynamic panel selection by Panel Architect."""
    topic = state["topic"]
    dossier = state["research_dossier"]
    domain_hint = state.get("domain_hint")
    
    panel_output = PanelArchitect.construct_panel(
        topic=topic,
        dossier=dossier,
        domain_hint=domain_hint
    )
    return {"panel": panel_output.participants}

def validate_panel_node(state: DebateState) -> Dict[str, Any]:
    """Node: Guarantee mandatory Public presence and valid panel bounds."""
    panel = state.get("panel", [])
    topic = state["topic"]
    dossier = state["research_dossier"]
    
    from models.schemas import PanelSelectionOutput
    validated_output = PanelArchitect.enforce_public_representation(
        PanelSelectionOutput(participants=panel),
        topic=topic,
        dossier=dossier
    )
    
    # Initialize round speaker tracking
    turn_counts = {p.id: 0 for p in validated_output.participants}
    
    return {
        "panel": validated_output.participants,
        "current_speaker_turns_this_round": turn_counts,
        "panel_validation_attempts": state.get("panel_validation_attempts", 0) + 1
    }

def opening_positions_node(state: DebateState) -> Dict[str, Any]:
    """Node: Generate Round 1 opening baseline statements for all panelists."""
    panel = state["panel"]
    topic = state["topic"]
    dossier = state["research_dossier"]
    
    messages: List[DebateMessage] = []
    claims: Dict[str, ClaimRecord] = {}
    snapshots: List[PositionSnapshot] = []
    edges: List[InfluenceEdge] = []
    
    for idx, panelist in enumerate(panel, start=1):
        msg = DebateAgent.generate_turn(
            speaker=panelist,
            topic=topic,
            dossier=dossier,
            recent_messages=messages,
            claims=claims,
            current_round=1,
            turn_index=idx,
            is_opening=True
        )
        messages.append(msg)
        
        # Register opening claim
        claim_id = f"CLM_R1_{idx:02d}"
        claims[claim_id] = ClaimRecord(
            id=claim_id,
            speaker_id=panelist.id,
            claim_text=f"Opening stance: {panelist.documented_position}",
            source_ids=msg.cited_source_ids,
            status="supported" if msg.cited_source_ids else "unverified",
            round_introduced=1,
            message_id=msg.id
        )
        
        # Register initial position snapshot
        snapshots.append(
            PositionSnapshot(
                speaker_id=panelist.id,
                round=1,
                stated_position=panelist.documented_position,
                confidence_level="firm",
                rationale="Opening statement baseline"
            )
        )
        
        # Register source citations as edges
        for src in msg.cited_source_ids:
            edges.append(
                InfluenceEdge(
                    source_node=panelist.id,
                    target_node=src,
                    edge_type="cited",
                    justifying_message_ids=[msg.id],
                    evidence_ids=[src]
                )
            )

    # Round 1 is complete; prepare for reactive Round 2
    turn_counts = {p.id: 0 for p in panel}
    
    return {
        "messages": messages,
        "claims": claims,
        "position_snapshots": snapshots,
        "influence_edges": edges,
        "current_round": 2,
        "current_speaker_turns_this_round": turn_counts
    }

def select_next_speaker_node(state: DebateState) -> Dict[str, Any]:
    """
    Node: Reactive Turn-Taking Heuristic.
    Picks speaker based on:
    1. Unanswered challenge from previous message
    2. Public representative if technical voices dominate
    3. Speaker with fewest turns this round
    """
    panel = state["panel"]
    messages = state.get("messages", [])
    turns_this_round = state.get("current_speaker_turns_this_round", {p.id: 0 for p in panel})
    last_message = messages[-1] if messages else None
    
    # Eligible panelists who have not exceeded turn quota in this round
    eligible = [p for p in panel if turns_this_round.get(p.id, 0) == 0]
    if not eligible:
        eligible = panel # All spoke once, allow second turns if needed
        
    next_speaker = eligible[0]
    
    # Priority 1: Directly challenged speaker
    if last_message and last_message.target_claim_ids:
        claims = state.get("claims", {})
        for cid in last_message.target_claim_ids:
            if cid in claims:
                target_speaker_id = claims[cid].speaker_id
                target_match = next((p for p in eligible if p.id == target_speaker_id), None)
                if target_match and target_match.id != last_message.speaker_id:
                    next_speaker = target_match
                    break

    # Priority 2: Public representation if last two were technical/institutions
    elif len(messages) >= 2:
        last_two_types = [
            next((p.identity_type for p in panel if p.id == m.speaker_id), "expert")
            for m in messages[-2:]
        ]
        if all(t in ("institution", "expert") for t in last_two_types):
            public_p = next((p for p in eligible if p.identity_type == "public_representative"), None)
            if public_p and public_p.id != (last_message.speaker_id if last_message else ""):
                next_speaker = public_p

    return {"next_speaker_id": next_speaker.id}

def generate_reaction_node(state: DebateState) -> Dict[str, Any]:
    """Node: Generate the selected speaker's reactive turn."""
    speaker_id = state["next_speaker_id"]
    panel = state["panel"]
    speaker = next((p for p in panel if p.id == speaker_id), panel[0])
    
    topic = state["topic"]
    dossier = state["research_dossier"]
    messages = state.get("messages", [])
    claims = state.get("claims", {})
    current_round = state.get("current_round", 2)
    
    turn_index = len(messages) + 1
    new_message = DebateAgent.generate_turn(
        speaker=speaker,
        topic=topic,
        dossier=dossier,
        recent_messages=messages,
        claims=claims,
        current_round=current_round,
        turn_index=turn_index,
        is_opening=False
    )
    
    # Update turns counter
    turns = dict(state.get("current_speaker_turns_this_round", {}))
    turns[speaker.id] = turns.get(speaker.id, 0) + 1
    
    return {
        "messages": messages + [new_message],
        "current_speaker_turns_this_round": turns
    }

def update_debate_state_node(state: DebateState) -> Dict[str, Any]:
    """Node: Ledger update for claims, concessions, and round transitions."""
    messages = state["messages"]
    last_msg = messages[-1]
    claims = dict(state.get("claims", {}))
    edges = list(state.get("influence_edges", []))
    
    # 1. Register new claim from this reactive turn
    new_claim_id = f"CLM_R{last_msg.round}_{len(claims) + 1:02d}"
    claims[new_claim_id] = ClaimRecord(
        id=new_claim_id,
        speaker_id=last_msg.speaker_id,
        claim_text=last_msg.content[:160] + "...",
        source_ids=last_msg.cited_source_ids,
        status="supported" if last_msg.cited_source_ids else "unverified",
        round_introduced=last_msg.round,
        message_id=last_msg.id
    )
    
    # 2. Add edges for challenges
    for target_cid in last_msg.target_claim_ids:
        if target_cid in claims:
            target_claim = claims[target_cid]
            target_claim.status = "disputed"
            target_claim.challenged_by_claim_ids.append(new_claim_id)
            edges.append(
                InfluenceEdge(
                    source_node=last_msg.speaker_id,
                    target_node=target_claim.speaker_id,
                    edge_type="challenged",
                    justifying_message_ids=[last_msg.id],
                    evidence_ids=last_msg.cited_source_ids
                )
            )

    # 3. Add edges for concessions
    for conc in last_msg.explicit_concessions:
        edges.append(
            InfluenceEdge(
                source_node=last_msg.speaker_id,
                target_node="panel_consensus",
                edge_type="conceded",
                justifying_message_ids=[last_msg.id],
                evidence_ids=[]
            )
        )

    # 4. Check if current round has completed (each panelist spoke)
    turns = state.get("current_speaker_turns_this_round", {})
    panel = state["panel"]
    round_finished = all(turns.get(p.id, 0) >= 1 for p in panel)
    
    current_round = state["current_round"]
    if round_finished:
        current_round += 1
        turns = {p.id: 0 for p in panel} # reset for next round

    return {
        "claims": claims,
        "influence_edges": edges,
        "current_round": current_round,
        "current_speaker_turns_this_round": turns
    }

def observer_analysis_node(state: DebateState) -> Dict[str, Any]:
    """Node: Independent Observer round analysis."""
    round_num = state["current_round"] - 1 # analyzed just-completed round
    messages = state["messages"]
    panel = state["panel"]
    claims = state["claims"]
    dossier = state["research_dossier"]
    
    round_messages = [m for m in messages if m.round == round_num]
    if not round_messages:
        round_messages = messages[-len(panel):]
        
    update = ObserverEngine.analyze_round(
        round_num=round_num,
        round_messages=round_messages,
        panel=panel,
        existing_claims=claims,
        dossier=dossier
    )
    
    all_updates = list(state.get("observer_updates", []))
    all_updates.append(update)
    
    return {"observer_updates": all_updates}

def final_report_node(state: DebateState) -> Dict[str, Any]:
    """Node: Generate objective final report and persist to SQLite."""
    topic = state["topic"]
    panel = state["panel"]
    messages = state["messages"]
    claims = state["claims"]
    updates = state.get("observer_updates", [])
    dossier = state["research_dossier"]
    
    report = ObserverEngine.generate_final_report(
        topic=topic,
        panel=panel,
        messages=messages,
        claims=claims,
        updates=updates,
        dossier=dossier
    )
    
    # Save to SQLite persistence
    session_id = state.get("session_id", str(uuid.uuid4())[:8])
    try:
        _persistence_service.save_session(
            session_id=session_id,
            topic=topic,
            domain_hint=state.get("domain_hint"),
            sources=state.get("sources", []),
            panel=panel,
            messages=messages,
            claims=claims,
            edges=state.get("influence_edges", []),
            final_report=report,
            status="completed"
        )
        logger.info(f"Debate session {session_id} saved successfully to SQLite.")
    except Exception as e:
        logger.error(f"Failed to persist session to SQLite: {e}")

    return {"final_report": report, "session_id": session_id}
