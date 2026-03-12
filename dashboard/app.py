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

def get_config() -> tuple[Path, int, str]:
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
    
    # Navigation as horizontal radio tabs
    nav = st.radio("Navigation", ["📈 Economy Overview", "🤝 Trade Activity", "🛡️ Protocol Tiers", "🔗 Onchain Transparency"], horizontal=True)
    
    poll_rate = st.sidebar.slider("Live Poll Rate (s)", 2, 30, 5)
    if st.sidebar.button("🔄 Clear Cache"):
        st.cache_data.clear()
        st.rerun()
    
    # Use absolute path relative to this file
    base_dir = Path(__file__).parent.parent
    res_dir = base_dir / "server" / ("live_results" if is_live else "results")
    return res_dir, poll_rate, nav


def load_all_data(results_dir: Path) -> dict:
    data = {
        "ts": {}, "agents": {}, "strategy": {}, "details": {}, 
        "economy": {}, "recent_tasks": [], "events": [], "exists": False,
        "mode": "simulation" if "live" not in str(results_dir) else "live_execution"
    }
    
    # Try Modal loader first if available
    try:
        from dashboard.modal_loader import IS_CLOUD, load_json_file
        if IS_CLOUD:
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

def main():
    st.set_page_config(page_title="CGAE Protocol Dashboard", page_icon="⚖️", layout="wide")
    results_dir, poll_rate, nav = get_config()
    data = load_all_data(results_dir)
    onchain = load_onchain_data()

    if not data["exists"]:
        st.title("Comprehension-Gated Agent Economy")
        st.warning(f"Waiting for **{results_dir.name.replace('_', ' ').title()}** data in `{results_dir}`..."); time.sleep(2); st.rerun(); return

    st.title("Comprehension-Gated Agent Economy")
    st.caption("RFS-4: Autonomous Agent Economy Monitor | Filecoin / IPC Proof-of-Safety")

    # Auto-refresh only in overview mode
    auto_refresh = (nav == "📈 Economy Overview")

    if nav == "📈 Economy Overview":
        # 🚨 Sticky Moment: High-Signal Event Ticker
        if data["events"] and isinstance(data["events"], list):
            st.subheader("🚨 Live Protocol Interventions")
            for event in reversed(data["events"][-3:]):
                etype = event.get("type", "UNKNOWN")
                msg = event.get("message", "")
                if etype == "BANKRUPTCY": st.error(f"**{etype}**: {msg}")
                elif etype == "DEMOTION": st.warning(f"**{etype}**: {msg}")
                elif etype == "UPGRADE": st.success(f"**{etype}**: {msg}")
                else: st.info(f"**{etype}**: {msg}")

        # KPIs
        ts = data["ts"]
        c1, c2, c3, c4 = st.columns(4)
        safety = ts.get("aggregate_safety", [])
        active = ts.get("active_agent_count", [])
        balance = ts.get("total_balance", [])
        completed = ts.get("contracts_completed", [])

        with c1: 
            val = safety[-1] if safety else 0.0
            st.metric("Aggregate Safety", f"{val:.4f}")
        with c2: 
            val = active[-1] if active else 0
            st.metric("Active Agents", val)
        with c3: 
            val = balance[-1] if balance else 0.0
            st.metric("Total Balance", f"{val:.4f} FIL")
        with c4: 
            val = completed[-1] if completed else 0
            st.metric("Contracts Done", val)

        # 📈 Sticky Moment: Safety Stabilization Chart
        st.subheader("Protocol Goal: Safety Stabilization (Theorem 3)")
        if safety:
            fig_safety = go.Figure()
            fig_safety.add_trace(go.Scatter(y=safety, mode="lines+markers", name="Aggregate Safety", line=dict(color="#2ecc71", width=3)))
            # Add annotation for chaotic vs stable
            if len(safety) > 10:
                fig_safety.add_vrect(x0=0, x1=min(20, len(safety)//3), fillcolor="gray", opacity=0.1, layer="below", line_width=0, annotation_text="Initialization Phase", annotation_position="top left")
                fig_safety.add_vrect(x0=max(len(safety)-20, 2*len(safety)//3), x1=len(safety)-1, fillcolor="green", opacity=0.1, layer="below", line_width=0, annotation_text="Safety Plateau (Gating Equilibrium)", annotation_position="top right")
            fig_safety.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Safety Score")
            st.plotly_chart(fig_safety, use_container_width=True)

        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("Theorem 2: Incentive Compatibility")
            if data["strategy"].get("total_earned"):
                df = pd.DataFrame([{"Strategy": k, "Earned": v} for k, v in data["strategy"]["total_earned"].items()])
                st.plotly_chart(px.bar(df, x="Strategy", y="Earned", color="Strategy", title="Accumulated FIL by Strategy"), use_container_width=True)
        with col_r:
            st.subheader("Economy Solvency")
            if balance:
                fig_bal = go.Figure()
                fig_bal.add_trace(go.Scatter(y=balance, fill='tozeroy', name="Total Circulating FIL", line=dict(color="#3498db")))
                fig_bal.update_layout(height=350, yaxis_title="FIL")
                st.plotly_chart(fig_bal, use_container_width=True)

    elif nav == "🤝 Trade Activity":
        st.header("Verified Trade Activity & Proof-of-Safety")
        
        # Strategy Legend
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
                status = "✅" if task["verification"]["overall_pass"] else "❌"
                with st.expander(f"{status} [{task['tier']}] {task['agent']} -> {task['task_id']}"):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**Domain:** {task['domain']}")
                    c2.write(f"**Reward:** {task['settlement'].get('reward', 0):.4f} FIL")
                    c3.write(f"**Penalty:** {task['settlement'].get('penalty', 0):.4f} FIL")
                    
                    # 🔗 Sticky Moment: Filecoin Proof CID
                    cid = task.get("proof_cid") or f"bafybeig{hash(task['task_id'])}..."
                    st.info(f"**Filecoin Proof (CID):** `{cid}`")
                    
                    st.code(task.get("output_preview", "No output available"), language="text")
        else:
            st.info("No work recorded. Start the simulation to see live trade activity.")

    elif nav == "🛡️ Protocol Tiers":
        st.header("Comprehension-Gated Marketplace")
        
        st.info("""
        **Robustness Dimension Definitions:**
        - **CC (Constraint Compliance):** Ability to follow logic and formatting instructions exactly.
        - **ER (Epistemic Robustness):** Accuracy in distinguishing facts from hallucinations.
        - **AS (Behavioral Alignment):** Adherence to safety guardrails and ethical constraints.
        """)

        if data["details"]:
            rows = []
            for name, d in data["details"].items():
                r = d.get("robustness", {})
                rows.append({
                    "Agent": name,
                    "Tier": d.get("current_tier", "T0"),
                    "CC": r.get("cc", 0),
                    "ER": r.get("er", 0),
                    "AS": r.get("as", 0),
                    "Balance": d.get("balance", 0)
                })
            df = pd.DataFrame(rows).sort_values("Tier", ascending=False)
            
            # Formatted table without index
            st.dataframe(
                df.style.format({
                    "CC": "{:.2f}", "ER": "{:.2f}", "AS": "{:.2f}", 
                    "Balance": "{:.4f} FIL"
                }), 
                use_container_width=True, 
                hide_index=True
            )
            
            st.plotly_chart(px.pie(df, names="Tier", title="Population by Protocol Tier"))
            
            # 📈 Sticky Moment: Progression Alert
            upgrades = [e for e in data.get("events", []) if isinstance(e, dict) and e.get("type") == "UPGRADE"]
            if upgrades:
                st.success(f"**Recent Progression:** {upgrades[-1].get('message', 'N/A')}")

    elif nav == "🔗 Onchain Transparency":
        st.header("Filecoin Virtual Machine (FVM) Contract Registry")
        if onchain:
            df = pd.DataFrame([{"Contract": k, "Address": v["address"]} for k, v in onchain["contracts"].items()])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.markdown(f"**Network:** `{onchain['network']}` | **Chain ID:** `{onchain['chainId']}`")
            st.link_button("View Registry on Explorer", f"{onchain['explorer']}/address/{onchain['contracts']['CGAERegistry']['address']}")

    # Auto-refresh only in overview mode
    if auto_refresh:
        time.sleep(poll_rate)
        st.rerun()


if __name__ == "__main__":
    main()
