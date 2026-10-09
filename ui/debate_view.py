from __future__ import annotations
import streamlit as st
from typing import List, Dict
from models.schemas import DebateMessage, Source

def render_debate_feed(messages: List[DebateMessage], sources: List[Source]):
    """Render the structured multi-round debate feed."""
    if not messages:
        st.info("The debate has not started yet. Enter a topic and initiate the simulation above.")
        return

    # Map sources for quick reference lookups
    source_map = {s.id: s for s in sources}

    # Group messages by round
    rounds: Dict[int, List[DebateMessage]] = {}
    for m in messages:
        rounds.setdefault(m.round, []).append(m)

    for round_num in sorted(rounds.keys()):
        round_title = "Round 1: Opening Baseline Positions" if round_num == 1 else f"Round {round_num}: Reactive Dialogue & Challenges"
        st.subheader(f"🗣️ {round_title}")

        for msg in rounds[round_num]:
            # Choose avatar icon
            avatar = "👥" if "public" in msg.speaker_id.lower() or "citizen" in msg.speaker_name.lower() else "🎙️"
            
            with st.chat_message(name=msg.speaker_name, avatar=avatar):
                st.markdown(f"**{msg.speaker_name}** `[{msg.id}]`")
                st.write(msg.content)

                # Render metadata badges
                cols = st.columns([1, 1, 1])
                
                # Citations
                if msg.cited_source_ids:
                    with cols[0]:
                        citations_text = ", ".join([
                            f"[{cid}]({source_map[cid].url if cid in source_map else '#'}"
                            for cid in msg.cited_source_ids
                        ])
                        st.caption(f"📚 **Cited Evidence:** {citations_text}")

                # Targets
                if msg.target_claim_ids:
                    with cols[1]:
                        st.caption(f"🎯 **Targeted Claims:** {', '.join(msg.target_claim_ids)}")

                # Concessions or Shifting
                if msg.explicit_concessions:
                    with cols[2]:
                        st.caption(f"🤝 **Concessions:** {'; '.join(msg.explicit_concessions)}")

                if msg.position_shift:
                    st.info(f"🔄 **Position Shift:** {msg.position_shift}")
                
                if msg.unresolved_questions:
                    with st.expander("❓ Raised Questions"):
                        for q in msg.unresolved_questions:
                            st.write(f"- {q}")

        st.divider()
