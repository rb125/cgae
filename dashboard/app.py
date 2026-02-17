"""
CGAE Economy Dashboard - Interactive visualization of the agent economy.

Displays:
- Real-time aggregate safety (Theorem 3)
- Agent balances, tiers, and survival rates
- Contract completion/failure rates
- Per-strategy performance comparison (Theorem 2 validation)
- Economic flow (rewards, penalties, storage costs)
- Tier distribution over time

Run: streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

RESULTS_DIR = Path("simulation/results")


@st.cache_data
def load_time_series() -> dict:
    path = RESULTS_DIR / "time_series.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


@st.cache_data
def load_agent_metrics() -> dict:
    path = RESULTS_DIR / "agent_metrics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


@st.cache_data
def load_strategy_summary() -> dict:
    path = RESULTS_DIR / "strategy_summary.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


@st.cache_data
def load_agent_details() -> dict:
    path = RESULTS_DIR / "agent_details.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


@st.cache_data
def load_economy_state() -> dict:
    path = RESULTS_DIR / "economy_state.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="CGAE Economy Dashboard",
        page_icon="⚖️",
        layout="wide",
    )

    st.title("Comprehension-Gated Agent Economy")
    st.caption("RFS-4: Autonomous Agent Economy Testbed")

    # Load data
    ts = load_time_series()
    agents = load_agent_metrics()
    strategy = load_strategy_summary()
    details = load_agent_details()
    economy = load_economy_state()

    if not ts:
        st.warning(
            "No simulation results found. Run the simulation first:\n\n"
            "```\npython -m simulation.runner\n```"
        )
        return

    # ------------------------------------------------------------------
    # Top-level KPIs
    # ------------------------------------------------------------------

    st.header("Economy Overview")
    col1, col2, col3, col4, col5 = st.columns(5)

    safety = ts.get("aggregate_safety", [])
    balances = ts.get("total_balance", [])
    active = ts.get("active_agent_count", [])
    completed = ts.get("contracts_completed", [])
    failed = ts.get("contracts_failed", [])

    with col1:
        val = safety[-1] if safety else 0
        delta = val - safety[0] if len(safety) > 1 else 0
        st.metric("Aggregate Safety", f"{val:.4f}", f"{delta:+.4f}")
    with col2:
        st.metric("Active Agents", active[-1] if active else 0)
    with col3:
        st.metric("Total Balance", f"{balances[-1]:.4f} FIL" if balances else "0")
    with col4:
        st.metric("Contracts Done", completed[-1] if completed else 0)
    with col5:
        st.metric("Contracts Failed", failed[-1] if failed else 0)

    # ------------------------------------------------------------------
    # Theorem 3: Aggregate Safety Over Time
    # ------------------------------------------------------------------

    st.header("Theorem 3: Monotonic Safety Scaling")

    if safety:
        fig_safety = go.Figure()
        fig_safety.add_trace(go.Scatter(
            x=ts["timestamps"], y=safety,
            mode="lines", name="Aggregate Safety S(P)",
            line=dict(color="#2ecc71", width=2),
        ))
        fig_safety.update_layout(
            yaxis_title="Aggregate Safety",
            xaxis_title="Time Step",
            height=350,
            margin=dict(l=50, r=20, t=30, b=40),
        )
        st.plotly_chart(fig_safety, use_container_width=True)

        monotonic = all(
            safety[i] <= safety[i+1] + 0.01
            for i in range(len(safety)-1)
        )
        if monotonic:
            st.success("Theorem 3 HOLDS: Aggregate safety is monotonically non-decreasing (within noise).")
        else:
            st.warning("Theorem 3 VIOLATED: Safety decreased at some point. See post-mortem analysis.")

    # ------------------------------------------------------------------
    # Theorem 2: Strategy Comparison
    # ------------------------------------------------------------------

    st.header("Theorem 2: Incentive-Compatible Robustness Investment")

    col_a, col_b = st.columns(2)

    with col_a:
        if strategy.get("total_earned"):
            df_earned = pd.DataFrame([
                {"Strategy": k, "Total Earned (FIL)": v}
                for k, v in strategy["total_earned"].items()
            ])
            fig_earned = px.bar(
                df_earned, x="Strategy", y="Total Earned (FIL)",
                color="Strategy", title="Total Earnings by Strategy",
            )
            fig_earned.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig_earned, use_container_width=True)

            adaptive = strategy["total_earned"].get("adaptive", 0)
            aggressive = strategy["total_earned"].get("aggressive", 0)
            if adaptive > aggressive:
                st.success(
                    f"Theorem 2 HOLDS: Adaptive ({adaptive:.4f}) > Aggressive ({aggressive:.4f}). "
                    "Robustness investment is incentive-compatible."
                )
            else:
                st.warning(
                    f"Theorem 2 NEEDS INVESTIGATION: Adaptive ({adaptive:.4f}) vs Aggressive ({aggressive:.4f})"
                )

    with col_b:
        if strategy.get("survival"):
            df_survival = pd.DataFrame([
                {"Strategy": k, "Survived": v}
                for k, v in strategy["survival"].items()
            ])
            fig_surv = px.bar(
                df_survival, x="Strategy", y="Survived",
                color="Strategy", title="Survival by Strategy",
            )
            fig_surv.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig_surv, use_container_width=True)

    # ------------------------------------------------------------------
    # Agent Balances Over Time
    # ------------------------------------------------------------------

    st.header("Agent Economics")

    if agents.get("balances"):
        fig_bal = go.Figure()
        for name, bal_series in agents["balances"].items():
            fig_bal.add_trace(go.Scatter(
                x=ts["timestamps"][:len(bal_series)],
                y=bal_series,
                mode="lines",
                name=name,
            ))
        fig_bal.update_layout(
            yaxis_title="Balance (FIL)",
            xaxis_title="Time Step",
            height=400,
            margin=dict(l=50, r=20, t=30, b=40),
        )
        st.plotly_chart(fig_bal, use_container_width=True)

    # ------------------------------------------------------------------
    # Agent Tiers Over Time
    # ------------------------------------------------------------------

    if agents.get("tiers"):
        fig_tiers = go.Figure()
        for name, tier_series in agents["tiers"].items():
            fig_tiers.add_trace(go.Scatter(
                x=ts["timestamps"][:len(tier_series)],
                y=tier_series,
                mode="lines",
                name=name,
            ))
        fig_tiers.update_layout(
            yaxis_title="Tier",
            xaxis_title="Time Step",
            yaxis=dict(dtick=1, range=[-0.5, 5.5]),
            height=350,
            margin=dict(l=50, r=20, t=30, b=40),
        )
        st.plotly_chart(fig_tiers, use_container_width=True)

    # ------------------------------------------------------------------
    # Economic Flow
    # ------------------------------------------------------------------

    st.header("Economic Flow")

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        rewards = ts.get("rewards_paid", [])
        penalties = ts.get("penalties_collected", [])
        if rewards:
            fig_flow = go.Figure()
            fig_flow.add_trace(go.Scatter(
                x=ts["timestamps"], y=rewards,
                mode="lines", name="Cumulative Rewards",
                line=dict(color="#27ae60"),
            ))
            fig_flow.add_trace(go.Scatter(
                x=ts["timestamps"], y=penalties,
                mode="lines", name="Cumulative Penalties",
                line=dict(color="#e74c3c"),
            ))
            fig_flow.update_layout(
                yaxis_title="FIL", xaxis_title="Time Step",
                height=350, title="Rewards vs Penalties",
            )
            st.plotly_chart(fig_flow, use_container_width=True)

    with col_e2:
        if completed:
            fig_contracts = go.Figure()
            fig_contracts.add_trace(go.Scatter(
                x=ts["timestamps"], y=completed,
                mode="lines", name="Completed",
                line=dict(color="#27ae60"),
            ))
            fig_contracts.add_trace(go.Scatter(
                x=ts["timestamps"], y=failed,
                mode="lines", name="Failed",
                line=dict(color="#e74c3c"),
            ))
            fig_contracts.update_layout(
                yaxis_title="Count", xaxis_title="Time Step",
                height=350, title="Contract Outcomes",
            )
            st.plotly_chart(fig_contracts, use_container_width=True)

    # ------------------------------------------------------------------
    # Agent Details Table
    # ------------------------------------------------------------------

    st.header("Agent Details")

    if details:
        rows = []
        for name, d in details.items():
            r = d.get("robustness") or {}
            rows.append({
                "Agent": name,
                "Strategy": d.get("strategy", ""),
                "Status": d.get("status", ""),
                "Tier": d.get("current_tier", ""),
                "Balance": f"{d.get('balance', 0):.4f}",
                "Earned": f"{d.get('total_earned', 0):.4f}",
                "Penalties": f"{d.get('total_penalties', 0):.4f}",
                "Completed": d.get("contracts_completed", 0),
                "Failed": d.get("contracts_failed", 0),
                "CC": f"{r.get('cc', 0):.3f}",
                "ER": f"{r.get('er', 0):.3f}",
                "AS": f"{r.get('as', 0):.3f}",
                "IH*": f"{r.get('ih', 0):.3f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # ------------------------------------------------------------------
    # Post-Mortem
    # ------------------------------------------------------------------

    st.header("Post-Mortem Analysis")

    if details:
        st.subheader("Key Findings")

        # Who survived?
        survived = [n for n, d in details.items() if d.get("status") == "active"]
        failed_agents = [n for n, d in details.items() if d.get("status") != "active"]

        st.markdown(f"**Survivors:** {', '.join(survived) if survived else 'None'}")
        st.markdown(f"**Failed:** {', '.join(failed_agents) if failed_agents else 'None'}")

        # Highest earner
        if details:
            top = max(details.items(), key=lambda x: x[1].get("total_earned", 0))
            st.markdown(f"**Top earner:** {top[0]} ({top[1].get('total_earned', 0):.4f} FIL)")

        # Binding dimensions
        st.subheader("Binding Robustness Dimensions")
        for name, d in details.items():
            r = d.get("true_robustness", d.get("robustness", {}))
            if r:
                dims = {"CC": r.get("cc", 0), "ER": r.get("er", 0), "AS": r.get("as", 0)}
                weakest = min(dims, key=dims.get)
                st.markdown(f"- **{name}**: weakest = {weakest} ({dims[weakest]:.3f})")


if __name__ == "__main__":
    main()
