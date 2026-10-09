from __future__ import annotations
import streamlit as st
from typing import List, Dict, Optional
from models.schemas import (
    ClaimRecord,
    InfluenceEdge,
    Panelist,
    ObserverRoundUpdate,
    FinalReport,
)
from ui.components import render_influence_network_graph

def render_observer_dashboard(
    panel: List[Panelist],
    claims: Dict[str, ClaimRecord],
    edges: List[InfluenceEdge],
    updates: List[ObserverRoundUpdate],
    final_report: Optional[FinalReport] = None
):
    """Render the Observer analytical dashboard with ledger, network, and final synthesis."""
    tab_graph, tab_ledger, tab_shifts, tab_report = st.tabs([
        "🕸️ Influence Network",
        "📋 Claim Ledger",
        "🧭 Narrative Timeline",
        "📑 Final Report"
    ])

    # 1. Influence Network
    with tab_graph:
        st.write("Visual representation of typed interactions (`challenged`, `supported`, `cited`, `conceded`).")
        render_influence_network_graph(panel, edges)
        
        if edges:
            with st.expander("Detailed Interaction Logs"):
                for e in edges:
                    st.caption(f"**{e.source_node}** `{e.edge_type}` **{e.target_node}** via `{', '.join(e.justifying_message_ids)}`")

    # 2. Claim Ledger
    with tab_ledger:
        st.write("Structured repository of substantive assertions made by participants.")
        if not claims:
            st.info("No claims recorded yet.")
        else:
            status_filter = st.selectbox("Filter Claims by Status", ["All", "supported", "disputed", "unverified"])
            for cid, c in claims.items():
                if status_filter != "All" and c.status != status_filter:
                    continue

                status_color = "green" if c.status == "supported" else "orange" if c.status == "disputed" else "gray"
                st.markdown(
                    f"**`[{c.id}]`** :{status_color}[● {c.status.upper()}] | Made by **{c.speaker_id}** in Round {c.round_introduced} (`{c.message_id}`)"
                )
                st.write(f"> {c.claim_text}")
                if c.source_ids:
                    st.caption(f"📚 Sources: {', '.join(c.source_ids)}")
                if c.challenged_by_claim_ids:
                    st.caption(f"⚔️ Challenged by: {', '.join(c.challenged_by_claim_ids)}")
                st.divider()

    # 3. Narrative Shifts
    with tab_shifts:
        if not updates:
            st.info("Observer updates will appear after each completed round.")
        else:
            for upd in updates:
                st.subheader(f"Round {upd.round} Observer Log")
                if upd.narrative_shifts:
                    st.write("**Framing & Shifts:**")
                    for s in upd.narrative_shifts:
                        st.write(f"- {s}")
                if upd.unsupported_assertions:
                    st.warning(f"**Unsupported Assertions:** {', '.join(upd.unsupported_assertions)}")
                if upd.unresolved_questions:
                    st.info(f"**Unresolved Questions:** {', '.join(upd.unresolved_questions)}")
                st.divider()

    # 4. Final Report
    with tab_report:
        if not final_report:
            st.info("The Final Report will be generated upon completion of all 3 rounds.")
        else:
            st.subheader(f"Synthesis Report: {final_report.topic}")
            st.markdown(f"### Narrative Evolution Summary\n{final_report.narrative_evolution_summary}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### ✅ Established Facts")
                for f in final_report.established_facts:
                    st.write(f"- {f}")
                st.markdown("#### ❓ Unresolved Questions")
                for q in final_report.unresolved_questions:
                    st.write(f"- {q}")

            with c2:
                st.markdown("#### ⚡ Disputed Interpretations")
                for d in final_report.disputed_interpretations:
                    st.write(f"- {d}")
                st.markdown("#### 🔍 Evidence Gaps")
                for g in final_report.evidence_gaps:
                    st.write(f"- {g}")
