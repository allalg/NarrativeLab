# NarrativeLab ⚖️

> **A dynamic, evidence-based multi-agent debate simulator**  
> Powered by **LangChain • LangGraph • OpenAI • Streamlit • Tavily / DuckDuckGo**

NarrativeLab turns real-world controversies and current events into structured, evidence-grounded debates. The system researches a topic, identifies relevant stakeholders, selects a dynamic panel with a **mandatory Public voice**, orchestrates a 3-round reactive conversation, and uses an independent **Observer** to analyze claims, citations, concessions, and influence patterns.

---

## 🌟 Key Features

1. **Credit-Preserving Hybrid Search**:
   - Uses **Tavily Basic Search** (1 credit per query) strictly for the primary topic briefing.
   - Uses **DuckDuckGo** (0 credits / free) for secondary perspective queries.
   - Automatically falls back to DuckDuckGo if no Tavily API key is provided or credits run low.
2. **Dynamic Panel Architecture with Mandatory Public Voice**:
   - 4 to 6 stakeholders dynamically chosen from evidence.
   - Enforces the invariant that a **Public Representative** is always on the panel to voice citizen/consumer interests.
3. **Reactive Multi-Turn Dialogue**:
   - Participants directly challenge opponent claim IDs and acknowledge concessions.
   - Grounded strictly in verified `SRC_XX` citations.
4. **Traceable Independent Observer**:
   - Maintains a claim ledger with statuses: `supported`, `contradicted`, `disputed`, `unverified`.
   - Records typed influence edges (`challenged`, `supported`, `cited`, `conceded`, `revised_after`) linked to message IDs.
5. **Interactive Streamlit UI & SQLite Persistence**:
   - Visual Plotly influence network graph.
   - Live claim ledger & timeline.
   - Automatic local saving of sessions in SQLite (`data/sessions.db`).

---

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Activate the virtual environment
.venv\Scripts\activate   # On Windows
source .venv/bin/activate # On Unix/macOS

# Copy environment template
cp .env.example .env
```

### 2. Configure API Keys in `.env`

```ini
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
TAVILY_API_KEY=tvly-...    # Optional: for 1-credit basic search
SEARCH_PROVIDER=hybrid     # 'hybrid', 'duckduckgo', or 'tavily'
```

### 3. Run the Streamlit Application

```bash
streamlit run app.py
```

### 4. Run the Test Suite

```bash
pytest tests/
```

---

## 📂 Project Architecture

```text
NarrativeLab/
├── app.py                      # Main Streamlit UI entry point
├── requirements.txt            # Dependency specifications
├── .env.example                # API configuration template
├── graph/                      # LangGraph state machine
│   ├── state.py                # TypedDict global state
│   ├── workflow.py             # StateGraph builder and conditional edge routers
│   └── nodes.py                # Pipeline nodes (research, panel, dialogue, observer)
├── agents/                     # Specialized agent roles
│   ├── panel_architect.py      # Dynamic panel constructor & Public role enforcer
│   ├── debate_agent.py         # Reactive debater with evidence citation
│   └── observer.py             # Claim extractor, influence tracker, final synthesizer
├── services/                   # External services
│   ├── search.py               # Hybrid Tavily (1 credit) + DuckDuckGo search
│   ├── evidence.py             # Deduplication and citation validation
│   └── persistence.py          # SQLite database storage (data/sessions.db)
├── models/                     # Data schemas & prompts
│   ├── schemas.py              # Pydantic v2 domain schemas
│   └── prompts.py              # LLM system prompts
├── ui/                         # Streamlit components
│   ├── components.py           # Custom styling & Plotly network graph
│   ├── debate_view.py          # 3-round reactive chat feed
│   ├── observer_view.py        # Influence network, claim ledger & reports
│   └── evidence_view.py        # Source dossier browser
└── tests/                      # Automated test suite
```
