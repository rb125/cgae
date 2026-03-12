"""
CGAE Economy Dashboard - High-Signal Protocol Monitoring
Optimized for Winning the Room (RFS-4 Hackathon).

Sticky Moments Focus:
- Bankruptcies & Suspensions
- On-chain Demotions/Expirations
- Robustness-driven Tier Upgrades
- Filecoin CID verification
"""

from __future__ import annotations
import json
import time
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def get_config() -> tuple[Path, int, bool, str, bool]:
    st.sidebar.title("CGAE Protocol Control")

    is_cloud = False
    try:
        from dashboard.modal_loader import IS_CLOUD

        is_cloud = IS_CLOUD
    except Exception:
        pass

    # Stripe-style toggle for Live vs Simulation
    is_live = st.sidebar.toggle(
        "Live Execution Mode",
        value=is_cloud,
        help="Toggle between Simulation (Synthetic) and Live Execution (Real LLMs)",
    )
    mode_label = "Live Execution" if is_live else "Simulation"
    st.sidebar.info(f"Viewing: **{mode_label}**")

    use_modal_backend = st.sidebar.toggle(
        "Use Modal Backend",
        value=is_cloud,
        help="When off, dashboard reads local files from server/live_results or server/results.",
    )
    if use_modal_backend and not is_cloud:
        st.sidebar.caption("Modal endpoint not configured; local files will be used.")
    
    poll_rate = st.sidebar.slider("Live Poll Rate (s)", 2, 30, 5)
    auto_refresh = st.sidebar.toggle("Auto Refresh", value=True)
    if st.sidebar.button("🔄 Clear Cache"):
        st.cache_data.clear()
        st.rerun()
    
    # Use absolute path relative to this file
    base_dir = Path(__file__).parent.parent
    res_dir = base_dir / "server" / ("live_results" if is_live else "results")
    return res_dir, poll_rate, auto_refresh, mode_label, use_modal_backend


def load_all_data(results_dir: Path, use_modal_backend: bool = True) -> dict:
    data = {
        "ts": {}, "agents": {}, "strategy": {}, "details": {}, 
        "economy": {}, "recent_tasks": [], "events": [], "exists": False,
        "mode": "simulation" if "live" not in str(results_dir) else "live_execution"
    }
    
    # Try Modal loader first if available
    try:
        from dashboard.modal_loader import IS_CLOUD, load_json_file
        if IS_CLOUD and use_modal_backend:
            # Load from Modal endpoints
            for key, filename in [("economy", "economy_state.json"), 
                                  ("details", "agent_details.json"),
                                  ("recent_tasks", "task_results.json"),
                                  ("events", "protocol_events.json")]:
                loaded = load_json_file(filename)
                if loaded:
                    data[key] = loaded
                    data["exists"] = True
            
            # Load mode-specific files
            if data["mode"] == "simulation":
                ts_data = load_json_file("time_series.json")
                if ts_data:
                    data["ts"] = ts_data
                data["agents"] = load_json_file("agent_metrics.json") or {}
                data["strategy"] = load_json_file("strategy_summary.json") or {}
            else:
                summary = load_json_file("final_summary.json")
                if summary:
                    data["exists"] = True
                    traj = summary.get("safety_trajectory", [])
                    data["ts"] = {
                        "timestamps": [t["time"] for t in traj],
                        "aggregate_safety": [t["safety"] for t in traj],
                        "active_agent_count": [t["active_agents"] for t in traj],
                        "total_balance": [t["total_balance"] for t in traj],
                        "contracts_completed": [],
                        "contracts_failed": []
                    }
                    rounds = load_json_file("round_summaries.json") or []
                    if rounds:
                        c_comp, c_fail = 0, 0
                        for r in rounds:
                            c_comp += r.get("tasks_passed", 0)
                            c_fail += r.get("tasks_failed", 0)
                            data["ts"]["contracts_completed"].append(c_comp)
                            data["ts"]["contracts_failed"].append(c_fail)
                    data["strategy"] = {"total_earned": {a["model_name"]: a["total_earned"] for a in summary.get("agents", [])}}
            
            return data
    except ImportError:
        pass  # Modal loader not available, fall back to filesystem
    
    # Filesystem fallback (local development)
    if not results_dir.exists():
        return data

    for key, filename in [("economy", "economy_state.json"), 
                          ("details", "agent_details.json"),
                          ("recent_tasks", "task_results.json"),
                          ("events", "protocol_events.json")]:
        path = results_dir / filename
        if path.exists():
            data[key] = json.loads(path.read_text())
            data["exists"] = True

    if data["mode"] == "simulation":
        ts_path = results_dir / "time_series.json"
        if ts_path.exists():
            data["ts"] = json.loads(ts_path.read_text()); data["exists"] = True
        metrics_path = results_dir / "agent_metrics.json"
        if metrics_path.exists(): data["agents"] = json.loads(metrics_path.read_text())
        strategy_path = results_dir / "strategy_summary.json"
        if strategy_path.exists(): data["strategy"] = json.loads(strategy_path.read_text())
    else:
        summary_path = results_dir / "final_summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text()); data["exists"] = True
            traj = summary.get("safety_trajectory", [])
            data["ts"] = {
                "timestamps": [t["time"] for t in traj],
                "aggregate_safety": [t["safety"] for t in traj],
                "active_agent_count": [t["active_agents"] for t in traj],
                "total_balance": [t["total_balance"] for t in traj],
                "contracts_completed": [],
                "contracts_failed": []
            }
            rounds_path = results_dir / "round_summaries.json"
            if rounds_path.exists():
                rounds = json.loads(rounds_path.read_text())
                if rounds:  # Only process if not empty
                    c_comp, c_fail = 0, 0
                    for r in rounds:
                        c_comp += r.get("tasks_passed", 0); c_fail += r.get("tasks_failed", 0)
                        data["ts"]["contracts_completed"].append(c_comp); data["ts"]["contracts_failed"].append(c_fail)
            data["strategy"] = {"total_earned": {a["model_name"]: a["total_earned"] for a in summary.get("agents", [])}}
    return data


@st.cache_data
def load_onchain_data():
    base_dir = Path(__file__).parent.parent
    path = base_dir / "contracts" / "deployed.json"
    return json.loads(path.read_text()) if path.exists() else None


# ---------------------------------------------------------------------------
# Dashboard Components
# ---------------------------------------------------------------------------

COLORWAY = ["#0f766e", "#f59e0b", "#2563eb", "#dc2626", "#0ea5e9", "#14b8a6"]
CARTESIAN_TRACE_TYPES = {"bar", "scatter", "scattergl", "histogram", "box", "violin", "candlestick", "ohlc"}


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        :root {
            --text-color: #0f172a;
            --background-color: #f8fafc;
            --secondary-background-color: #eef2f7;
        }

        html, body, [class*="css"] {
            font-family: "Space Grotesk", "Segoe UI", sans-serif;
            color: #0f172a;
        }

        [data-testid="stSidebar"] *,
        [data-testid="stMetricLabel"] *,
        [data-testid="stMetricValue"] *,
        [data-testid="stMarkdownContainer"] *,
        [data-baseweb="tab-list"] *,
        [data-baseweb="tab"] * {
            color: #0f172a !important;
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 0% 0%, rgba(20, 184, 166, 0.12), transparent 42%),
                radial-gradient(circle at 100% 0%, rgba(245, 158, 11, 0.10), transparent 36%),
                linear-gradient(180deg, #f8fafc 0%, #f0fdf4 55%, #eff6ff 100%);
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(15, 118, 110, 0.08) 0%, rgba(255, 255, 255, 0.75) 50%, rgba(245, 158, 11, 0.08) 100%);
            border-right: 1px solid rgba(15, 118, 110, 0.18);
        }

        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
            max-width: 1200px;
        }

        [data-testid="stMetric"] {
            border-radius: 12px;
            border: 1px solid rgba(15, 118, 110, 0.18);
            background: rgba(255, 255, 255, 0.84);
            padding: 0.25rem 0.35rem;
        }

        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"],
        [data-testid="stMetricDelta"] {
            justify-content: flex-start !important;
            text-align: left !important;
            align-items: flex-start !important;
        }

        [data-testid="stMetricLabel"] > div,
        [data-testid="stMetricValue"] > div,
        [data-testid="stMetricDelta"] > div {
            text-align: left !important;
        }

        [data-testid="stExpander"] {
            border-radius: 12px;
            border: 1px solid rgba(15, 118, 110, 0.18);
            background: rgba(255, 255, 255, 0.78);
        }

        [data-testid="stDataFrame"] {
            border-radius: 12px;
            border: 1px solid rgba(15, 118, 110, 0.18);
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            background: rgba(255, 255, 255, 0.82);
        }

        button[kind="secondary"] {
            border-radius: 999px;
            border: 1px solid rgba(15, 118, 110, 0.26);
            background: rgba(255, 255, 255, 0.75);
        }

        [data-testid="stLinkButton"] a {
            background: #0f766e !important;
            border: 1px solid #0f766e !important;
            color: #ffffff !important;
            border-radius: 10px !important;
        }

        [data-testid="stLinkButton"] a:hover {
            background: #115e59 !important;
            border-color: #115e59 !important;
            color: #ffffff !important;
        }

        [data-testid="stLinkButton"] a * {
            color: #ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def style_figure(fig: go.Figure, *, yaxis_title: str = "", height: int = 350) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        colorway=COLORWAY,
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0.72)",
        font={"family": "Space Grotesk, sans-serif", "color": "#0f172a"},
        legend={"orientation": "h", "y": 1.08, "x": 0},
        margin={"l": 16, "r": 16, "t": 16, "b": 16},
        height=height,
    )
    is_cartesian = any((getattr(trace, "type", None) or "") in CARTESIAN_TRACE_TYPES for trace in fig.data)
    if is_cartesian:
        fig.update_xaxes(showgrid=True, gridcolor="rgba(15,23,42,0.08)", zeroline=False)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(15,23,42,0.08)", zeroline=False)
        if yaxis_title:
            fig.update_yaxes(title=yaxis_title)
    return fig


def render_header(data: dict, mode_label: str, poll_rate: int) -> None:
    ts = data.get("ts", {})
    timestamps = ts.get("timestamps", [])
    active = ts.get("active_agent_count", [])
    st.title("Comprehension-Gated Agent Economy")
    st.caption("RFS-4 Autonomous Agent Economy Monitor | Filecoin / IPC Proof-of-Safety")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Mode", mode_label)
    with c2:
        st.metric("Latest Snapshot", str(timestamps[-1]) if timestamps else "n/a")
    with c3:
        st.metric("Tracked Agents", active[-1] if active else 0)
    st.caption(f"Auto-refresh interval: {poll_rate}s")


def render_event_feed(events: list[dict]) -> None:
    if not events:
        return
    st.subheader("Live Protocol Interventions")
    for event in reversed(events[-5:]):
        etype = str(event.get("type", "UNKNOWN")).upper()
        message = str(event.get("message", "No detail available"))
        payload = f"**{etype}**: {message}"
        if etype in {"BANKRUPTCY", "CIRCUMVENTION_BLOCKED"}:
            st.error(payload)
        elif etype == "DEMOTION":
            st.warning(payload)
        elif etype == "UPGRADE":
            st.success(payload)
        else:
            st.info(payload)

def main():
    st.set_page_config(page_title="CGAE Protocol Dashboard", page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")
    inject_theme()
    results_dir, poll_rate, auto_refresh, mode_label, use_modal_backend = get_config()
    data = load_all_data(results_dir, use_modal_backend=use_modal_backend)
    onchain = load_onchain_data()
    render_header(data, mode_label, poll_rate)
    try:
        from dashboard.modal_loader import IS_CLOUD
        using_modal = use_modal_backend and IS_CLOUD
    except Exception:
        using_modal = False

    if using_modal:
        st.caption("Data source: Modal backend endpoint")
    else:
        st.caption(f"Data source: local files in `{results_dir}`")

    if not data["exists"]:
        status_note = None
        try:
            from dashboard.modal_loader import IS_CLOUD, get_backend_health

            if IS_CLOUD:
                health = get_backend_health()
                status = health.get("status", "unknown")
                status_note = f"Backend status: `{status}`"
                if status == "running":
                    st.success(status_note)
                elif status == "stale":
                    age = int(health.get("age_seconds", 0))
                    st.error(f"{status_note} (last heartbeat {age}s ago)")
                elif status == "down":
                    st.error(status_note)
                else:
                    st.info(status_note)
        except Exception:
            pass

        wait_msg = f"Waiting for **{results_dir.name.replace('_', ' ').title()}** data in `{results_dir}`..."
        if status_note:
            wait_msg = f"{wait_msg}\n\n{status_note}"
        st.warning(wait_msg)
        if auto_refresh:
            time.sleep(max(2, poll_rate))
            st.rerun()
        return

    tab_overview, tab_trade, tab_tiers, tab_onchain = st.tabs(
        ["📈 Economy Overview", "🤝 Trade Activity", "🛡️ Protocol Tiers", "🔗 Onchain Transparency"]
    )

    with tab_overview:
        if data["events"] and isinstance(data["events"], list):
            render_event_feed(data["events"])

        ts = data["ts"]
        safety = ts.get("aggregate_safety", [])
        active = ts.get("active_agent_count", [])
        balance = ts.get("total_balance", [])
        completed = ts.get("contracts_completed", [])

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Aggregate Safety", f"{(safety[-1] if safety else 0.0):.4f}")
        with m2:
            st.metric("Active Agents", active[-1] if active else 0)
        with m3:
            st.metric("Total Balance", f"{(balance[-1] if balance else 0.0):.4f} FIL")
        with m4:
            st.metric("Contracts Done", completed[-1] if completed else 0)

        st.subheader("Protocol Goal: Safety Stabilization (Theorem 3)")
        if safety:
            fig_safety = go.Figure()
            fig_safety.add_trace(
                go.Scatter(
                    y=safety,
                    mode="lines+markers",
                    name="Aggregate Safety",
                    line={"color": "#0f766e", "width": 3},
                    marker={"size": 6, "color": "#0f766e"},
                )
            )
            if len(safety) > 10:
                fig_safety.add_vrect(
                    x0=0,
                    x1=min(20, len(safety) // 3),
                    fillcolor="rgba(30,41,59,0.10)",
                    opacity=0.35,
                    layer="below",
                    line_width=0,
                    annotation_text="Initialization",
                    annotation_position="top left",
                )
                fig_safety.add_vrect(
                    x0=max(len(safety) - 20, 2 * len(safety) // 3),
                    x1=len(safety) - 1,
                    fillcolor="rgba(15,118,110,0.14)",
                    opacity=0.45,
                    layer="below",
                    line_width=0,
                    annotation_text="Stabilization",
                    annotation_position="top right",
                )
            style_figure(fig_safety, yaxis_title="Safety Score", height=360)
            st.plotly_chart(fig_safety, use_container_width=True)

        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("Theorem 2: Incentive Compatibility")
            if data["strategy"].get("total_earned"):
                earned_df = pd.DataFrame(
                    [{"Strategy": k, "Earned": v} for k, v in data["strategy"]["total_earned"].items()]
                )
                fig_earned = px.bar(
                    earned_df,
                    x="Strategy",
                    y="Earned",
                    color="Strategy",
                    title="Accumulated FIL by Strategy",
                    color_discrete_sequence=COLORWAY,
                )
                fig_earned.update_traces(marker_line_width=0, opacity=0.9)
                style_figure(fig_earned, yaxis_title="FIL Earned")
                st.plotly_chart(fig_earned, use_container_width=True)

        with col_r:
            st.subheader("Economy Solvency")
            if balance:
                fig_bal = go.Figure()
                fig_bal.add_trace(
                    go.Scatter(
                        y=balance,
                        fill="tozeroy",
                        name="Total Circulating FIL",
                        line={"color": "#0ea5e9", "width": 3},
                        fillcolor="rgba(14,165,233,0.14)",
                    )
                )
                style_figure(fig_bal, yaxis_title="FIL", height=360)
                st.plotly_chart(fig_bal, use_container_width=True)

    with tab_trade:
        st.header("Verified Trade Activity & Proof-of-Safety")

        passed = sum(1 for task in data.get("recent_tasks", []) if task.get("verification", {}).get("overall_pass"))
        failed = max(len(data.get("recent_tasks", [])) - passed, 0)
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Recent Tasks", len(data.get("recent_tasks", [])))
        with m2:
            st.metric("Passes", passed)
        with m3:
            st.metric("Fails", failed)

        with st.expander("ℹ️ Agent Strategy Guide"):
            st.markdown("""
            - **Conservative:** High robustness, low risk. Only bids on T1 tasks.
            - **Balanced:** Moderate risk, target moderate rewards.
            - **Aggressive:** Chases high T1 rewards, ignores robustness; fails at higher tiers.
            - **Adaptive:** Re-invests 15% of profits into robustness audits to unlock higher tiers.
            - **Cheater:** Tries to bypass gates; heavily penalized upon failure.
            """)

        if data["recent_tasks"]:
            for task in reversed(data["recent_tasks"][-15:]):
                verification = task.get("verification", {})
                status = "✅" if verification.get("overall_pass") else "❌"
                with st.expander(f"{status} [{task.get('tier', 'T0')}] {task.get('agent', 'unknown')} -> {task.get('task_id', 'n/a')}"):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**Domain:** {task.get('domain', 'n/a')}")
                    c2.write(f"**Reward:** {task.get('settlement', {}).get('reward', 0):.4f} FIL")
                    c3.write(f"**Penalty:** {task.get('settlement', {}).get('penalty', 0):.4f} FIL")
                    cid = task.get("proof_cid") or f"bafybeig{hash(task.get('task_id', 'unknown'))}..."
                    st.info(f"**Filecoin Proof (CID):** `{cid}`")
                    st.code(task.get("output_preview", "No output available"), language="text")
        else:
            st.info("No work recorded. Start the simulation to see live trade activity.")

    with tab_tiers:
        st.header("Comprehension-Gated Marketplace")
        st.info(
            "Robustness dimensions: CC (Constraint Compliance), ER (Epistemic Robustness), AS (Behavioral Alignment)."
        )

        if data["details"]:
            rows = []
            for name, details in data["details"].items():
                robustness = details.get("robustness", {})
                rows.append(
                    {
                        "Agent": name,
                        "Tier": details.get("current_tier", "T0"),
                        "CC": robustness.get("cc", 0),
                        "ER": robustness.get("er", 0),
                        "AS": robustness.get("as", 0),
                        "Balance": details.get("balance", 0),
                    }
                )
            tiers_df = pd.DataFrame(rows).sort_values("Tier", ascending=False)
            st.dataframe(
                tiers_df.style.format({"CC": "{:.2f}", "ER": "{:.2f}", "AS": "{:.2f}", "Balance": "{:.4f} FIL"}),
                use_container_width=True,
                hide_index=True,
            )

            c_left, c_right = st.columns((1, 1.2))
            with c_left:
                fig_tier = px.pie(
                    tiers_df,
                    names="Tier",
                    title="Population by Protocol Tier",
                    color_discrete_sequence=COLORWAY,
                )
                style_figure(fig_tier, height=340)
                st.plotly_chart(fig_tier, use_container_width=True)

            with c_right:
                robust_df = tiers_df.melt(
                    id_vars=["Agent", "Tier"],
                    value_vars=["CC", "ER", "AS"],
                    var_name="Dimension",
                    value_name="Score",
                )
                fig_robust = px.bar(
                    robust_df,
                    x="Agent",
                    y="Score",
                    color="Dimension",
                    barmode="group",
                    title="Robustness Profile by Agent",
                    color_discrete_sequence=["#0f766e", "#f59e0b", "#2563eb"],
                )
                fig_robust.update_traces(marker_line_width=0)
                style_figure(fig_robust, yaxis_title="Score", height=340)
                st.plotly_chart(fig_robust, use_container_width=True)

            upgrades = [
                event
                for event in data.get("events", [])
                if isinstance(event, dict) and event.get("type") == "UPGRADE"
            ]
            if upgrades:
                st.success(f"Recent progression: {upgrades[-1].get('message', 'N/A')}")

    with tab_onchain:
        st.header("Filecoin Virtual Machine (FVM) Contract Registry")
        if onchain:
            contracts_df = pd.DataFrame(
                [{"Contract": name, "Address": contract["address"]} for name, contract in onchain["contracts"].items()]
            )
            st.dataframe(contracts_df, use_container_width=True, hide_index=True)
            st.info(f"Network: {onchain['network']} | Chain ID: {onchain['chainId']}")
            st.link_button(
                "View Registry on Explorer",
                f"{onchain['explorer']}/address/{onchain['contracts']['CGAERegistry']['address']}",
            )

    if auto_refresh:
        time.sleep(poll_rate)
        st.rerun()


if __name__ == "__main__":
    main()
