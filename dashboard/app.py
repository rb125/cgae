"""
CGAE Protocol Dashboard — Solana Edition
Dark crypto dashboard UI. Solana-native on-chain layer, Filecoin audit storage.
"""
from __future__ import annotations
import json, time
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

try:
    from streamlit import st_autorefresh
except ImportError:
    st_autorefresh = None

# ── Theme constants ───────────────────────────────────────────────────────────
BG          = "#0a0f1e"
BG2         = "#0f1629"
CARD        = "rgba(255,255,255,0.04)"
BORDER      = "rgba(139,92,246,0.25)"
ACCENT      = "#8b5cf6"       # Solana purple
ACCENT2     = "#14f195"       # Solana green
ACCENT3     = "#f59e0b"       # amber
RED         = "#ef4444"
BLUE        = "#3b82f6"
TEXT        = "#e2e8f0"
MUTED       = "#64748b"
MONO        = "'IBM Plex Mono', 'Fira Code', monospace"
COLORWAY    = [ACCENT2, ACCENT, ACCENT3, BLUE, RED, "#06b6d4"]

# ── CSS injection ─────────────────────────────────────────────────────────────
THEME_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
    color: {TEXT};
    background-color: {BG};
}}

[data-testid="stAppViewContainer"] {{
    background: radial-gradient(ellipse 80% 50% at 50% -20%, rgba(139,92,246,0.15), transparent),
                radial-gradient(ellipse 60% 40% at 80% 80%, rgba(20,241,149,0.08), transparent),
                {BG};
}}

section[data-testid="stSidebar"] {{
    background: {BG2};
    border-right: 1px solid {BORDER};
}}
section[data-testid="stSidebar"] * {{ color: {TEXT} !important; }}

.block-container {{ padding-top: 1.5rem; max-width: 1280px; }}

/* Metric cards */
[data-testid="stMetric"] {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 0.5rem 0.75rem;
    backdrop-filter: blur(12px);
}}
[data-testid="stMetricLabel"] p {{ color: {MUTED} !important; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; }}
[data-testid="stMetricValue"] div {{ color: {TEXT} !important; font-family: {MONO}; font-size: 1.4rem; }}
[data-testid="stMetricDelta"] div {{ font-family: {MONO}; font-size: 0.8rem; }}

/* Tabs */
[data-baseweb="tab-list"] {{ background: transparent; border-bottom: 1px solid {BORDER}; gap: 0; }}
[data-baseweb="tab"] {{ background: transparent !important; color: {MUTED} !important; border-radius: 0; padding: 0.6rem 1.2rem; font-size: 0.85rem; font-weight: 500; }}
[data-baseweb="tab"][aria-selected="true"] {{
    color: {ACCENT2} !important;
    border-bottom: 2px solid {ACCENT2} !important;
    background: transparent !important;
}}

/* Expanders */
[data-testid="stExpander"] {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    backdrop-filter: blur(8px);
}}
[data-testid="stExpander"] summary p {{ color: {TEXT} !important; }}

/* Dataframe */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    background: {CARD};
}}

/* Buttons */
button[kind="secondary"] {{
    background: {CARD} !important;
    border: 1px solid {BORDER} !important;
    color: {TEXT} !important;
    border-radius: 8px !important;
}}
[data-testid="stLinkButton"] a {{
    background: linear-gradient(135deg, {ACCENT}, #6d28d9) !important;
    border: none !important;
    color: #fff !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}}

/* Alerts */
[data-testid="stAlert"] {{ border-radius: 10px; border-left-width: 3px; }}

/* Scrollbar */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {BG2}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 3px; }}

/* Sidebar title */
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {{
    color: {ACCENT2} !important;
    font-size: 1rem !important;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}}
</style>
"""

# ── Data loading ──────────────────────────────────────────────────────────────

def _get_modal_loader():
    try:
        from dashboard import modal_loader
        return modal_loader
    except Exception:
        try:
            import modal_loader
            return modal_loader
        except Exception:
            return None


@st.cache_data(ttl=30)
def load_all_data() -> dict:
    data = {
        "ts": {}, "agents": {}, "strategy": {}, "details": {},
        "economy": {}, "recent_tasks": [], "events": [], "exists": False,
    }
    modal_loader = _get_modal_loader()
    if not modal_loader or not getattr(modal_loader, "IS_CLOUD", False):
        return data

    load_json_file = modal_loader.load_json_file
    available = set(modal_loader.list_available_files())
    if not available:
        return data

    for key, fname in [("economy", "economy_state.json"),
                       ("details", "agent_details.json"),
                       ("recent_tasks", "task_results.json"),
                       ("events", "protocol_events.json")]:
        if fname in available:
            loaded = load_json_file(fname)
            if loaded:
                data[key] = loaded
                data["exists"] = True

    if "final_summary.json" not in available:
        return data
    summary = load_json_file("final_summary.json")
    if not summary:
        return data

    data["exists"] = True
    traj = summary.get("safety_trajectory", [])
    if len(traj) > 500:
        traj = traj[::max(1, len(traj)//500)]

    agents_list = summary.get("agents", [])
    n = len(traj)
    total_c = sum(a.get("contracts_completed", 0) for a in agents_list)
    total_f = sum(a.get("contracts_failed", 0) for a in agents_list)

    data["ts"] = {
        "timestamps":        [t["time"] for t in traj],
        "aggregate_safety":  [t["safety"] for t in traj],
        "active_agent_count":[t["active_agents"] for t in traj],
        "total_balance":     [t["total_balance"] for t in traj],
        "contracts_completed":[round(total_c * i / n) for i in range(1, n+1)],
        "contracts_failed":  [round(total_f * i / n) for i in range(1, n+1)],
    }
    data["strategy"] = {
        "total_earned": {a["model_name"]: a["total_earned"] for a in agents_list}
    }
    return data


@st.cache_data
def load_deployed() -> dict | None:
    # Try Solana deployed.json first, fall back to EVM
    base = Path(__file__).parent.parent
    for p in [base/"solana_contracts"/"deployed.json", base/"contracts"/"deployed.json"]:
        if p.exists():
            return json.loads(p.read_text())
    return None


# ── Chart helpers ─────────────────────────────────────────────────────────────

def _fig(height=320) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        colorway=COLORWAY,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.03)",
        font={"family": "Inter, sans-serif", "color": TEXT, "size": 12},
        legend={"orientation": "h", "y": 1.08, "x": 0, "font": {"size": 11}},
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        height=height,
        xaxis={"showgrid": True, "gridcolor": "rgba(255,255,255,0.05)", "zeroline": False, "color": MUTED},
        yaxis={"showgrid": True, "gridcolor": "rgba(255,255,255,0.05)", "zeroline": False, "color": MUTED},
    )
    return fig


def _card(label: str, value: str, delta: str = "", color: str = ACCENT2) -> str:
    """Return an HTML stat card string."""
    delta_html = f'<div style="color:{ACCENT2};font-size:0.72rem;font-family:{MONO};margin-top:2px">{delta}</div>' if delta else ""
    return f"""
    <div style="background:{CARD};border:1px solid {BORDER};border-radius:12px;
                padding:1rem 1.25rem;backdrop-filter:blur(12px);">
        <div style="color:{MUTED};font-size:0.7rem;text-transform:uppercase;
                    letter-spacing:0.1em;margin-bottom:0.4rem">{label}</div>
        <div style="color:{color};font-family:{MONO};font-size:1.5rem;
                    font-weight:600;line-height:1">{value}</div>
        {delta_html}
    </div>"""


def _section(title: str) -> None:
    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;text-transform:uppercase;'
        f'letter-spacing:0.12em;margin:1.5rem 0 0.6rem;border-bottom:1px solid {BORDER};'
        f'padding-bottom:0.4rem">{title}</div>',
        unsafe_allow_html=True,
    )

# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar() -> tuple[int, bool, bool]:
    with st.sidebar:
        st.markdown(f'<div style="color:{ACCENT2};font-size:0.7rem;letter-spacing:0.15em;text-transform:uppercase;margin-bottom:0.25rem">CGAE Protocol</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:{TEXT};font-size:1.1rem;font-weight:700;margin-bottom:1.5rem">Agent Economy Monitor</div>', unsafe_allow_html=True)

        ml = _get_modal_loader()
        configured = bool(ml and getattr(ml, "IS_CLOUD", False))

        st.markdown(f'<div style="color:{MUTED};font-size:0.72rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem">Network</div>', unsafe_allow_html=True)
        net_color = ACCENT2 if configured else RED
        net_label = "● LIVE" if configured else "● OFFLINE"
        st.markdown(f'<div style="color:{net_color};font-family:{MONO};font-size:0.85rem;margin-bottom:1rem">{net_label}</div>', unsafe_allow_html=True)

        st.markdown(f'<div style="color:{MUTED};font-size:0.72rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem">Chain</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:{ACCENT};font-family:{MONO};font-size:0.85rem;margin-bottom:1rem">Solana Devnet</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:{MUTED};font-size:0.72rem;margin-bottom:1rem">Audit storage: Filecoin Calibnet</div>', unsafe_allow_html=True)

        st.divider()
        poll_rate = st.slider("Refresh interval (s)", 2, 30, 5)
        auto_refresh = st.toggle("Auto-refresh", value=True)
        if st.button("↺  Clear cache", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.markdown(f'<div style="color:{MUTED};font-size:0.68rem">Solana programs</div>', unsafe_allow_html=True)
        deployed = load_deployed()
        if deployed and "programs" in deployed:
            for name, pid in deployed["programs"].items():
                st.markdown(f'<div style="color:{MUTED};font-size:0.65rem">{name}</div><div style="color:{TEXT};font-family:{MONO};font-size:0.62rem;word-break:break-all;margin-bottom:0.4rem">{pid}</div>', unsafe_allow_html=True)
        elif deployed and "contracts" in deployed:
            # EVM fallback
            for name, c in deployed["contracts"].items():
                st.markdown(f'<div style="color:{MUTED};font-size:0.65rem">{name}</div><div style="color:{TEXT};font-family:{MONO};font-size:0.62rem;word-break:break-all;margin-bottom:0.4rem">{c["address"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="color:{MUTED};font-size:0.65rem">Not deployed yet</div>', unsafe_allow_html=True)

    return poll_rate, auto_refresh, configured


# ── Tab: Overview ─────────────────────────────────────────────────────────────

def tab_overview(data: dict) -> None:
    ts = data.get("ts", {})
    safety   = ts.get("aggregate_safety", [])
    active   = ts.get("active_agent_count", [])
    balance  = ts.get("total_balance", [])
    done     = ts.get("contracts_completed", [])
    failed   = ts.get("contracts_failed", [])

    # KPI row
    cols = st.columns(5)
    kpis = [
        ("Aggregate Safety", f"{safety[-1]:.4f}" if safety else "—", ACCENT2),
        ("Active Agents",    str(active[-1]) if active else "—",     ACCENT),
        ("Total Balance",    f"{balance[-1]:.3f} SOL" if balance else "—", TEXT),
        ("Contracts Done",   str(done[-1]) if done else "—",         ACCENT2),
        ("Contracts Failed", str(failed[-1]) if failed else "—",     RED),
    ]
    for col, (label, val, color) in zip(cols, kpis):
        with col:
            st.markdown(_card(label, val, color=color), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Events feed
    events = data.get("events", [])
    if events and isinstance(events, list):
        _section("Live Protocol Events")
        for ev in reversed(events[-4:]):
            etype = str(ev.get("type", "")).upper()
            msg   = ev.get("message", "")
            icon  = {"UPGRADE": "↑", "DEMOTION": "↓", "BANKRUPTCY": "✕",
                     "CIRCUMVENTION_BLOCKED": "⊘", "TEST_FIL_TOPUP": "⊕"}.get(etype, "·")
            color = {
                "UPGRADE": ACCENT2, "DEMOTION": ACCENT3,
                "BANKRUPTCY": RED, "CIRCUMVENTION_BLOCKED": RED,
            }.get(etype, MUTED)
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-left:3px solid {color};'
                f'border-radius:8px;padding:0.5rem 0.75rem;margin-bottom:0.4rem;font-size:0.82rem">'
                f'<span style="color:{color};font-family:{MONO};margin-right:0.5rem">{icon} {etype}</span>'
                f'<span style="color:{TEXT}">{msg}</span></div>',
                unsafe_allow_html=True,
            )

    # Safety chart
    _section("Aggregate Safety S(P) — Theorem 3")
    if safety:
        fig = _fig(300)
        x = list(range(len(safety)))
        fig.add_trace(go.Scatter(
            x=x, y=safety, mode="lines", name="S(P)",
            line={"color": ACCENT2, "width": 2},
            fill="tozeroy", fillcolor="rgba(20,241,149,0.06)",
        ))
        # Shade init / stabilization zones
        if len(safety) > 10:
            fig.add_vrect(x0=0, x1=len(safety)//5, fillcolor="rgba(255,255,255,0.03)",
                          layer="below", line_width=0,
                          annotation_text="Init", annotation_font_color=MUTED,
                          annotation_position="top left")
            fig.add_vrect(x0=4*len(safety)//5, x1=len(safety)-1,
                          fillcolor="rgba(20,241,149,0.05)",
                          layer="below", line_width=0,
                          annotation_text="Stable", annotation_font_color=ACCENT2,
                          annotation_position="top right")
        st.plotly_chart(fig, use_container_width=True)

    # Balance + contracts row
    c1, c2 = st.columns(2)
    with c1:
        _section("Economy Solvency")
        if balance:
            fig = _fig(260)
            fig.add_trace(go.Scatter(
                y=balance, mode="lines", name="Total SOL",
                line={"color": ACCENT, "width": 2},
                fill="tozeroy", fillcolor="rgba(139,92,246,0.08)",
            ))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        _section("Contract Flow")
        if done:
            fig = _fig(260)
            fig.add_trace(go.Scatter(y=done,   mode="lines", name="Completed", line={"color": ACCENT2, "width": 2}))
            fig.add_trace(go.Scatter(y=failed, mode="lines", name="Failed",    line={"color": RED,     "width": 2, "dash": "dot"}))
            st.plotly_chart(fig, use_container_width=True)

    # Strategy earnings
    earned = data.get("strategy", {}).get("total_earned", {})
    if earned:
        _section("Theorem 2 — Incentive Compatibility")
        df = pd.DataFrame([{"Agent": k, "SOL Earned": v} for k, v in earned.items()]).sort_values("SOL Earned", ascending=True)
        fig = _fig(max(200, len(df)*40))
        fig.add_trace(go.Bar(
            x=df["SOL Earned"], y=df["Agent"], orientation="h",
            marker={"color": COLORWAY[:len(df)], "opacity": 0.85},
        ))
        fig.update_layout(showlegend=False, xaxis_title="SOL Earned")
        st.plotly_chart(fig, use_container_width=True)


# ── Tab: Agents ───────────────────────────────────────────────────────────────

def tab_agents(data: dict) -> None:
    details = data.get("details", {})
    if not details:
        st.info("No agent data yet.")
        return

    rows = []
    for name, d in details.items():
        r = d.get("robustness") or {}
        rows.append({
            "Agent": name,
            "Tier": d.get("current_tier", "T0"),
            "CC": r.get("cc", 0),
            "ER": r.get("er", 0),
            "AS": r.get("as", 0),
            "Balance (SOL)": d.get("balance", 0),
            "Done": d.get("contracts_completed", 0),
            "Failed": d.get("contracts_failed", 0),
        })
    df = pd.DataFrame(rows).sort_values("Tier", ascending=False)

    _section("Agent Leaderboard")

    # Tier badge colors
    tier_colors = {"T5": ACCENT2, "T4": ACCENT2, "T3": ACCENT, "T2": ACCENT3, "T1": MUTED, "T0": RED}

    for _, row in df.iterrows():
        tc = tier_colors.get(row["Tier"], MUTED)
        with st.container():
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:10px;'
                f'padding:0.75rem 1rem;margin-bottom:0.5rem;display:flex;align-items:center;gap:1rem">'
                f'<span style="background:{tc}22;color:{tc};border:1px solid {tc}44;border-radius:6px;'
                f'padding:0.15rem 0.5rem;font-family:{MONO};font-size:0.75rem;font-weight:600">{row["Tier"]}</span>'
                f'<span style="color:{TEXT};font-weight:600;flex:1">{row["Agent"]}</span>'
                f'<span style="color:{MUTED};font-size:0.75rem;font-family:{MONO}">CC {row["CC"]:.2f} · ER {row["ER"]:.2f} · AS {row["AS"]:.2f}</span>'
                f'<span style="color:{ACCENT2};font-family:{MONO};font-size:0.85rem;margin-left:1rem">{row["Balance (SOL)"]:.4f} SOL</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        _section("Tier Distribution")
        tier_counts = df["Tier"].value_counts().reset_index()
        tier_counts.columns = ["Tier", "Count"]
        fig = _fig(280)
        fig.add_trace(go.Pie(
            labels=tier_counts["Tier"], values=tier_counts["Count"],
            hole=0.55,
            marker={"colors": COLORWAY, "line": {"color": BG, "width": 2}},
            textfont={"color": TEXT},
        ))
        fig.update_layout(showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        _section("Robustness Radar")
        fig = _fig(280)
        for i, row in df.iterrows():
            fig.add_trace(go.Scatterpolar(
                r=[row["CC"], row["ER"], row["AS"], row["CC"]],
                theta=["CC", "ER", "AS", "CC"],
                mode="lines",
                name=row["Agent"],
                line={"width": 2},
            ))
        fig.update_layout(
            polar={"radialaxis": {"range": [0, 1], "color": MUTED, "gridcolor": "rgba(255,255,255,0.08)"},
                   "angularaxis": {"color": MUTED},
                   "bgcolor": "rgba(0,0,0,0)"},
        )
        st.plotly_chart(fig, use_container_width=True)


# ── Tab: Tasks ────────────────────────────────────────────────────────────────

def tab_tasks(data: dict) -> None:
    tasks = data.get("recent_tasks", [])
    if not tasks:
        st.info("No task data yet.")
        return

    passed = sum(1 for t in tasks if t.get("verification", {}).get("overall_pass"))
    failed = len(tasks) - passed
    rate   = passed / len(tasks) * 100 if tasks else 0

    cols = st.columns(4)
    for col, (label, val, color) in zip(cols, [
        ("Total Tasks",   str(len(tasks)), TEXT),
        ("Passed",        str(passed),     ACCENT2),
        ("Failed",        str(failed),     RED),
        ("Pass Rate",     f"{rate:.1f}%",  ACCENT),
    ]):
        with col:
            st.markdown(_card(label, val, color=color), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    _section("Recent Task Executions")

    for task in reversed(tasks[-20:]):
        v      = task.get("verification", {})
        passed = v.get("overall_pass", False)
        icon   = "✓" if passed else "✕"
        color  = ACCENT2 if passed else RED
        tier   = task.get("tier", "T?")
        agent  = task.get("agent", "unknown")
        tid    = task.get("task_id", "n/a")
        reward = task.get("settlement", {}).get("reward", 0)
        cid    = task.get("proof_cid", "")

        with st.expander(f"{icon}  [{tier}]  {agent}  ·  {tid}"):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f'<span style="color:{MUTED};font-size:0.75rem">Domain</span><br><span style="color:{TEXT}">{task.get("domain","—")}</span>', unsafe_allow_html=True)
            c2.markdown(f'<span style="color:{MUTED};font-size:0.75rem">Reward</span><br><span style="color:{ACCENT2};font-family:{MONO}">{reward:.4f} SOL</span>', unsafe_allow_html=True)
            c3.markdown(f'<span style="color:{MUTED};font-size:0.75rem">Status</span><br><span style="color:{color};font-family:{MONO}">{icon} {"PASS" if passed else "FAIL"}</span>', unsafe_allow_html=True)
            if cid:
                st.markdown(f'<div style="background:rgba(20,241,149,0.05);border:1px solid rgba(20,241,149,0.2);border-radius:6px;padding:0.4rem 0.6rem;font-family:{MONO};font-size:0.72rem;color:{ACCENT2};margin-top:0.5rem">⬡ Filecoin CID: {cid}</div>', unsafe_allow_html=True)
            preview = task.get("output_preview", "")
            if preview:
                st.code(preview[:400], language="text")


# ── Tab: On-chain ─────────────────────────────────────────────────────────────

def tab_onchain(data: dict) -> None:
    deployed = load_deployed()

    _section("Deployed Programs")
    if deployed:
        network = deployed.get("network", deployed.get("cluster", "unknown"))
        chain   = deployed.get("chainId", deployed.get("chain", ""))
        explorer = deployed.get("explorer", "https://explorer.solana.com")

        st.markdown(
            f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:10px;'
            f'padding:1rem 1.25rem;margin-bottom:1rem">'
            f'<span style="color:{MUTED};font-size:0.72rem;text-transform:uppercase;letter-spacing:0.1em">Network</span>'
            f'<span style="color:{ACCENT2};font-family:{MONO};font-size:0.9rem;margin-left:1rem">{network}</span>'
            + (f'<span style="color:{MUTED};font-size:0.75rem;margin-left:1rem">Chain {chain}</span>' if chain else "")
            + f'</div>',
            unsafe_allow_html=True,
        )

        programs = deployed.get("programs", deployed.get("contracts", {}))
        for name, val in programs.items():
            addr = val if isinstance(val, str) else val.get("address", "")
            explorer_url = f"{explorer}/account/{addr}?cluster=devnet" if "solana" in explorer.lower() or not chain else f"{explorer}/address/{addr}"
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:10px;'
                f'padding:0.75rem 1rem;margin-bottom:0.5rem;display:flex;align-items:center;gap:1rem">'
                f'<span style="color:{ACCENT};font-weight:600;min-width:160px">{name}</span>'
                f'<span style="color:{TEXT};font-family:{MONO};font-size:0.78rem;flex:1;word-break:break-all">{addr}</span>'
                f'<a href="{explorer_url}" target="_blank" style="color:{ACCENT2};font-size:0.75rem;white-space:nowrap;'
                f'background:rgba(20,241,149,0.08);border:1px solid rgba(20,241,149,0.2);border-radius:6px;'
                f'padding:0.2rem 0.5rem;text-decoration:none">↗ Explorer</a>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f'<div style="color:{MUTED};font-size:0.85rem;padding:1rem">Programs not yet deployed. '
            f'Run <code style="color:{ACCENT2}">anchor build && anchor deploy --provider.cluster devnet</code></div>',
            unsafe_allow_html=True,
        )

    _section("Cross-Chain Architecture")
    st.markdown(
        f"""<div style="background:{CARD};border:1px solid {BORDER};border-radius:10px;padding:1.25rem;font-size:0.82rem;line-height:1.8">
        <div style="display:grid;grid-template-columns:1fr auto 1fr;gap:1rem;align-items:center;text-align:center">
            <div style="background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.3);border-radius:8px;padding:0.75rem">
                <div style="color:{ACCENT};font-weight:600;margin-bottom:0.25rem">Solana</div>
                <div style="color:{MUTED};font-size:0.75rem">Economic logic<br>Agent registry<br>Escrow &amp; settlement<br>CID anchoring</div>
            </div>
            <div style="color:{MUTED};font-size:1.2rem">⇄</div>
            <div style="background:rgba(20,241,149,0.06);border:1px solid rgba(20,241,149,0.2);border-radius:8px;padding:0.75rem">
                <div style="color:{ACCENT2};font-weight:600;margin-bottom:0.25rem">Filecoin</div>
                <div style="color:{MUTED};font-size:0.75rem">Audit certificate storage<br>CDCT + DDFT + EECT proofs<br>Immutable CID<br>Verifiable by anyone</div>
            </div>
        </div>
        <div style="color:{MUTED};font-size:0.72rem;margin-top:1rem;text-align:center">
            Audit flow: <span style="color:{TEXT}">audit_live()</span> → Filecoin CID →
            <span style="color:{ACCENT}">cgae_registry.certify()</span> → Solana Certification PDA
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Tier thresholds reference
    _section("Gate Function Thresholds")
    thresholds = [
        {"Tier": "T0", "CC": "0.00", "ER": "0.00", "AS": "0.00", "Budget": "0 SOL"},
        {"Tier": "T1", "CC": "0.30", "ER": "0.30", "AS": "0.25", "Budget": "0.01 SOL"},
        {"Tier": "T2", "CC": "0.50", "ER": "0.50", "AS": "0.45", "Budget": "0.1 SOL"},
        {"Tier": "T3", "CC": "0.65", "ER": "0.65", "AS": "0.60", "Budget": "1 SOL"},
        {"Tier": "T4", "CC": "0.80", "ER": "0.80", "AS": "0.75", "Budget": "10 SOL"},
        {"Tier": "T5", "CC": "0.90", "ER": "0.90", "AS": "0.85", "Budget": "100 SOL"},
    ]
    st.dataframe(pd.DataFrame(thresholds), hide_index=True, use_container_width=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="CGAE · Solana Protocol Dashboard",
        page_icon="◎",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(THEME_CSS, unsafe_allow_html=True)

    poll_rate, auto_refresh, configured = render_sidebar()

    # Header
    st.markdown(
        f'<div style="display:flex;align-items:baseline;gap:0.75rem;margin-bottom:0.25rem">'
        f'<span style="color:{ACCENT2};font-family:{MONO};font-size:0.75rem;letter-spacing:0.15em">◎ CGAE PROTOCOL</span>'
        f'</div>'
        f'<h1 style="color:{TEXT};font-size:1.75rem;font-weight:700;margin:0 0 0.25rem">Agent Economy Dashboard</h1>'
        f'<div style="color:{MUTED};font-size:0.82rem;margin-bottom:1.5rem">'
        f'Comprehension-Gated Agent Economy · Solana + Filecoin · Robustness-First Architecture</div>',
        unsafe_allow_html=True,
    )

    if not configured:
        st.markdown(
            f'<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
            f'min-height:50vh;gap:1rem;text-align:center">'
            f'<div style="font-size:2.5rem">◎</div>'
            f'<div style="color:{ACCENT2};font-size:1.2rem;font-weight:600">Backend not configured</div>'
            f'<div style="color:{MUTED};max-width:400px;font-size:0.85rem">'
            f'Set up the Modal backend or configure a local data source to view live economy data.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    with st.spinner(""):
        data = load_all_data()

    if not data["exists"]:
        st.markdown(
            f'<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
            f'min-height:50vh;gap:1rem;text-align:center">'
            f'<div style="width:40px;height:40px;border:2px solid {ACCENT};border-top-color:transparent;'
            f'border-radius:50%;animation:spin 1s linear infinite"></div>'
            f'<div style="color:{ACCENT2};font-size:1.1rem;font-weight:600">Economy initializing…</div>'
            f'<div style="color:{MUTED};font-size:0.82rem">Agents spinning up · First round in ~30s</div>'
            f'</div>'
            f'<style>@keyframes spin{{to{{transform:rotate(360deg)}}}}</style>',
            unsafe_allow_html=True,
        )
        if auto_refresh and st_autorefresh:
            st_autorefresh(interval=poll_rate * 1000, key="init_refresh")
        return

    t1, t2, t3, t4 = st.tabs(["◎  Overview", "⬡  Agents", "⚡  Tasks", "🔗  On-Chain"])
    with t1: tab_overview(data)
    with t2: tab_agents(data)
    with t3: tab_tasks(data)
    with t4: tab_onchain(data)

    if auto_refresh and st_autorefresh:
        st_autorefresh(interval=poll_rate * 1000, key="main_refresh")


if __name__ == "__main__":
    main()
