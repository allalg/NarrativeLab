from __future__ import annotations
import streamlit as st
from typing import Optional, List
from models.schemas import EvidenceDossier, Source

def render_evidence_dossier(dossier: Optional[EvidenceDossier], sources: List[Source]):
    """Render the evidence briefing and clickable source cards."""
    if not dossier and not sources:
        st.info("No research evidence retrieved yet.")
        return

    if dossier:
        st.markdown(f"### Research Briefing\n{dossier.topic_summary}")
        
        with st.expander("📅 Timeline & Background Events", expanded=False):
            for t in dossier.timeline:
                st.write(f"- {t}")

        with st.expander("⚡ Core Identified Disputes", expanded=True):
            for d in dossier.core_disputes:
                st.write(f"- {d}")

    st.subheader(f"Verified Evidence Sources ({len(sources)})")
    for s in sources:
        with st.container():
            col1, col2 = st.columns([1, 4])
            with col1:
                st.markdown(f"**`[{s.id}]`**")
                if s.publisher:
                    st.caption(f"*{s.publisher}*")
                if s.published_date:
                    st.caption(s.published_date)
            with col2:
                st.markdown(f"**[{s.title}]({s.url})**")
                st.write(s.snippet)
            st.divider()
