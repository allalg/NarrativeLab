from __future__ import annotations
import os
import uuid
import streamlit as st
from dotenv import load_dotenv

# Load local environment variables from .env
load_dotenv()

from models.schemas import (
    Source,
    EvidenceDossier,
    Panelist,
    DebateMessage,
    ClaimRecord,
    InfluenceEdge,
    ObserverRoundUpdate,
    FinalReport,
)
from graph.workflow import build_debate_graph
from services.persistence import PersistenceService
from ui import (
    apply_custom_styles,
    render_panelist_card,
    render_debate_feed,
    render_observer_dashboard,
    render_evidence_dossier,
)

# Page configuration
st.set_page_config(
    page_title="NarrativeLab | Multi-Agent Debate Simulator",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_custom_styles()
persistence = PersistenceService()

# -----------------------------------------------------------------------------
# Sidebar: Setup & History
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("⚖️ NarrativeLab")
    st.caption("Evidence-Grounded Multi-Agent Debate Simulator")
    st.divider()

    st.subheader("⚙️ API Configuration")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    current_model = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    current_base_url = os.getenv("OPENAI_BASE_URL", "")

    openai_input = st.text_input(
        "OpenAI API Key",
        value=openai_key,
        type="password",
        help="Required for dynamic debaters, panel architect, and observer."
    )
    if openai_input:
        os.environ["OPENAI_API_KEY"] = openai_input.strip()

    model_options = ["gpt-6-luna", "gpt-5.6-luna", "gpt-4o-mini", "gpt-4o", "custom"]
    selected_model_idx = model_options.index(current_model) if current_model in model_options else 0
    selected_model = st.selectbox(
        "LLM Model",
        model_options,
        index=selected_model_idx,
        help="Select model (default: gpt-6-luna for fast, cost-efficient agentic debates)"
    )
    if selected_model == "custom":
        custom_model = st.text_input("Custom Model Name", value=current_model)
        os.environ["OPENAI_MODEL"] = custom_model.strip()
    else:
        os.environ["OPENAI_MODEL"] = selected_model

    base_url_input = st.text_input(
        "API Base URL (Optional)",
        value=current_base_url,
        help="Custom endpoint if using a proxy, OpenRouter, or Azure (leave blank for standard OpenAI)."
    )
    if base_url_input:
        os.environ["OPENAI_BASE_URL"] = base_url_input.strip()
    elif "OPENAI_BASE_URL" in os.environ:
        del os.environ["OPENAI_BASE_URL"]

    tavily_input = st.text_input(
        "Tavily API Key (Optional)",
        value=tavily_key,
        type="password",
        help="Used for 1-credit basic search on primary queries."
    )
    if tavily_input:
        os.environ["TAVILY_API_KEY"] = tavily_input.strip()

    if st.button("🔍 Test API Connections", use_container_width=True):
        # Test OpenAI
        cur_openai = os.environ.get("OPENAI_API_KEY", "")
        cur_mod = os.environ.get("OPENAI_MODEL", "gpt-6-luna")
        cur_base = os.environ.get("OPENAI_BASE_URL")
        if not cur_openai:
            st.error("❌ OpenAI: Key missing")
        else:
            try:
                from openai import OpenAI
                client_kwargs = {"api_key": cur_openai}
                if cur_base:
                    client_kwargs["base_url"] = cur_base
                test_client = OpenAI(**client_kwargs)
                test_client.chat.completions.create(
                    model=cur_mod,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=3
                )
                st.success(f"✅ OpenAI Key: Connected successfully with {cur_mod}!")
            except Exception as e:
                st.error(f"❌ OpenAI Key Failed ({cur_mod}): {e}")

        # Test Tavily
        cur_tavily = os.environ.get("TAVILY_API_KEY", "")
        if cur_tavily:
            try:
                from tavily import TavilyClient
                t_client = TavilyClient(api_key=cur_tavily)
                t_client.search("test", max_results=1)
                st.success("✅ Tavily Key: Connected successfully!")
            except Exception as e:
                st.warning(f"⚠️ Tavily Key Warning: {e}")
        else:
            st.info("ℹ️ Tavily: Not set (Using DuckDuckGo free search)")

    search_mode = st.selectbox(
        "Search Strategy",
        ["hybrid", "duckduckgo", "tavily"],
        index=0,
        help="Hybrid uses 1 Tavily credit for topic dossier, and free DuckDuckGo for secondary searches."
    )
    os.environ["SEARCH_PROVIDER"] = search_mode

    st.divider()
    st.subheader("📂 Past Debates")
    sessions = persistence.list_sessions()
    if sessions:
        selected_session = st.selectbox(
            "Load Historical Session",
            options=["-- Select --"] + [f"{s['session_id']}: {s['topic'][:30]}..." for s in sessions]
        )
        if selected_session != "-- Select --":
            sess_id = selected_session.split(":")[0]
            if st.button("Load Selected Session"):
                loaded = persistence.load_session(sess_id)
                if loaded:
                    st.session_state["session_data"] = loaded
                    st.success(f"Loaded session {sess_id}!")
    else:
        st.caption("No saved debates yet.")

# -----------------------------------------------------------------------------
# Main Application Flow
# -----------------------------------------------------------------------------
st.title("⚖️ NarrativeLab: Reactive Multi-Agent Debate")
st.write(
    "Enter an ongoing real-world topic. NarrativeLab researches current sources, "
    "selects a topic-specific panel (with a mandatory Public voice), orchestrates a 3-round reactive debate, "
    "and deploys an independent Observer to chart claims and influence."
)

col_topic, col_domain, col_btn = st.columns([3, 2, 1])

with col_topic:
    topic_input = st.text_input(
        "Topic / Controversy / Event",
        placeholder="e.g., EU AI Act enforcement on open source foundation models"
    )

with col_domain:
    domain_hint = st.text_input(
        "Domain Hint (Optional)",
        placeholder="e.g., Technology Policy, Geopolitics, Public Health"
    )

with col_btn:
    st.write("")
    st.write("")
    start_debate = st.button("🚀 Start Debate", type="primary", use_container_width=True)

# -----------------------------------------------------------------------------
# Execution Runner
# -----------------------------------------------------------------------------
if start_debate:
    active_openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not topic_input.strip():
        st.error("Please enter a topic to debate.")
    elif not active_openai_key:
        st.error("OpenAI API Key is required. Please set it in the sidebar or in your .env file.")
    else:
        # Pre-flight check: verify OpenAI key connects
        try:
            from openai import OpenAI
            client_args = {"api_key": active_openai_key}
            if os.getenv("OPENAI_BASE_URL"):
                client_args["base_url"] = os.getenv("OPENAI_BASE_URL")
            client_check = OpenAI(**client_args)
            client_check.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=2
            )
        except Exception as auth_err:
            st.error(
                f"❌ **OpenAI Authentication Failed**: `{auth_err}`\n\n"
                "Your OpenAI API key was rejected by the OpenAI API server. "
                "Please verify that your key starts with `sk-proj-...` or `sk-...` "
                "and has active credits at [OpenAI API Keys](https://platform.openai.com/api-keys)."
            )
            st.stop()

        status_container = st.status("Executing NarrativeLab Pipeline...", expanded=True)
        session_id = str(uuid.uuid4())[:8]

        try:
            status_container.write("🔍 Phase 1: Researching topic and constructing evidence dossier...")
            graph = build_debate_graph()
            
            initial_state = {
                "session_id": session_id,
                "topic": topic_input.strip(),
                "domain_hint": domain_hint.strip() if domain_hint else None,
                "research_dossier": None,
                "sources": [],
                "panel": [],
                "panel_validation_attempts": 0,
                "current_round": 1,
                "max_rounds": 3,
                "messages": [],
                "claims": {},
                "position_snapshots": [],
                "influence_edges": [],
                "next_speaker_id": None,
                "current_speaker_turns_this_round": {},
                "unanswered_challenges": [],
                "observer_updates": [],
                "final_report": None,
                "errors": []
            }

            status_container.write("🏛️ Phase 2: Architecting balanced panel (enforcing mandatory Public role)...")
            status_container.write("🗣️ Phase 3: Running reactive 3-round debate and Observer tracking...")
            
            # Execute full graph
            final_output = graph.invoke(initial_state)
            
            status_container.update(label="✅ Debate & Observer Analysis Complete!", state="complete", expanded=False)
            
            # Store in session state for rendering
            st.session_state["active_state"] = final_output
            st.rerun()

        except Exception as e:
            status_container.update(label="❌ Pipeline Failed", state="error", expanded=True)
            st.error(f"Execution Error: {e}")

# -----------------------------------------------------------------------------
# Results Presentation
# -----------------------------------------------------------------------------
active_data = st.session_state.get("active_state")

if active_data:
    topic = active_data.get("topic", "Topic")
    panel = active_data.get("panel", [])
    sources = active_data.get("sources", [])
    dossier = active_data.get("research_dossier")
    messages = active_data.get("messages", [])
    claims = active_data.get("claims", {})
    edges = active_data.get("influence_edges", [])
    updates = active_data.get("observer_updates", [])
    final_report = active_data.get("final_report")

    st.subheader(f"📌 Active Topic: {topic}")

    main_tabs = st.tabs([
        "🗣️ Live Debate Transcript",
        "🕵️ Observer Dashboard",
        "👥 Debating Panel",
        "📚 Evidence Dossier"
    ])

    # Tab 1: Debate feed
    with main_tabs[0]:
        render_debate_feed(messages, sources)

    # Tab 2: Observer dashboard
    with main_tabs[1]:
        render_observer_dashboard(
            panel=panel,
            claims=claims,
            edges=edges,
            updates=updates,
            final_report=final_report
        )

    # Tab 3: Panelists
    with main_tabs[2]:
        st.write("Dynamic panel selected by Panel Architect grounded in retrieved evidence.")
        cols = st.columns(min(len(panel), 3) if panel else 1)
        for i, p in enumerate(panel):
            with cols[i % len(cols)]:
                render_panelist_card(p)

    # Tab 4: Evidence
    with main_tabs[3]:
        render_evidence_dossier(dossier, sources)
