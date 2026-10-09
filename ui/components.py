from __future__ import annotations
import streamlit as st
from typing import List, Dict, Any, Optional
import plotly.graph_objects as go
from models.schemas import Panelist, ClaimRecord, InfluenceEdge

CUSTOM_CSS = """
<style>
/* NarrativeLab Custom Styling */
.main {
    background-color: #0e1117;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 12px;
}
.stTabs [data-baseweb="tab"] {
    height: 48px;
    white-space: pre-wrap;
    background-color: #1a1f2c;
    border-radius: 8px 8px 0px 0px;
    padding: 8px 16px;
    color: #cbd5e1;
}
.stTabs [aria-selected="true"] {
    background-color: #2563eb !important;
    color: #ffffff !important;
    font-weight: 600;
}
.panel-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
}
.badge-public {
    background-color: #059669;
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}
.badge-expert {
    background-color: #3b82f6;
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}
.badge-institution {
    background-color: #8b5cf6;
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}
.claim-supported {
    color: #10b981;
    font-weight: 600;
}
.claim-disputed {
    color: #f59e0b;
    font-weight: 600;
}
.claim-unverified {
    color: #94a3b8;
    font-weight: 600;
}
</style>
"""

def apply_custom_styles():
    """Inject custom responsive styling."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

def render_panelist_card(panelist: Panelist):
    """Render a clean profile card for a debate participant."""
    badge_class = "badge-expert"
    if panelist.identity_type == "public_representative":
        badge_class = "badge-public"
    elif panelist.identity_type == "institution":
        badge_class = "badge-institution"

    badge_label = panelist.identity_type.replace("_", " ").title()

    html = f"""
    <div class="panel-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <h4 style="margin: 0; color: #f8fafc;">{panelist.display_name}</h4>
            <span class="{badge_class}">{badge_label}</span>
        </div>
        <p style="color: #94a3b8; font-size: 13px; margin: 0 0 8px 0;"><strong>Role:</strong> {panelist.role}</p>
        <p style="color: #cbd5e1; font-size: 13px; margin: 0 0 8px 0;"><em>"{panelist.documented_position}"</em></p>
        <div style="font-size: 12px; color: #64748b;">
            <strong>Selection Rationale:</strong> {panelist.selection_reason}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_influence_network_graph(panel: List[Panelist], edges: List[InfluenceEdge]):
    """Generate an interactive Plotly 2D influence network graph."""
    if not panel:
        st.info("No panelists active to construct graph.")
        return

    import math

    # Calculate circular layout coordinates for panelists
    node_x = []
    node_y = []
    node_text = []
    node_color = []
    node_id_map = {}

    num_nodes = len(panel)
    for i, p in enumerate(panel):
        angle = 2 * math.pi * i / num_nodes
        x = math.cos(angle)
        y = math.sin(angle)
        node_x.append(x)
        node_y.append(y)
        node_text.append(f"<b>{p.display_name}</b><br>{p.role}")
        node_color.append("#059669" if p.identity_type == "public_representative" else "#3b82f6")
        node_id_map[p.id] = (x, y)

    # Edge traces
    edge_x = []
    edge_y = []
    edge_colors = {
        "challenged": "#ef4444",
        "supported": "#10b981",
        "cited": "#60a5fa",
        "conceded": "#f59e0b",
        "responded_to": "#a855f7"
    }

    edge_traces = []
    for edge in edges:
        src = node_id_map.get(edge.source_node)
        tgt = node_id_map.get(edge.target_node)
        if src and tgt:
            color = edge_colors.get(edge.edge_type, "#94a3b8")
            edge_traces.append(
                go.Scatter(
                    x=[src[0], tgt[0], None],
                    y=[src[1], tgt[1], None],
                    line=dict(width=2, color=color),
                    hoverinfo="text",
                    text=f"{edge.source_node} --[{edge.edge_type}]--> {edge.target_node}",
                    mode="lines"
                )
            )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=[p.display_name.split()[0] for p in panel],
        textposition="top center",
        hovertext=node_text,
        hoverinfo="text",
        marker=dict(
            showscale=False,
            color=node_color,
            size=30,
            line=dict(width=2, color="#ffffff")
        )
    )

    fig = go.Figure(
        data=edge_traces + [node_trace],
        layout=go.Layout(
            title="Traceable Influence & Interaction Network",
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=20, r=20, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="#0f172a",
            paper_bgcolor="#0f172a",
            font=dict(color="#f8fafc")
        )
    )
    st.plotly_chart(fig, use_container_width=True)
