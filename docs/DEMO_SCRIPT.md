# Demo Video Script Guide

## Overview
5-minute demo showing CGAE's unique enforcement capabilities and Filecoin integration.

## Setup (Before Recording)

1. **Deploy contracts to Calibnet**
   ```bash
   cd contracts
   npm install
   export PRIVATE_KEY=<your_key>
   npm run deploy:calibnet
   ```

2. **Configure Filecoin storage**
   ```bash
   cd storage
   npm install
   export FILECOIN_PRIVATE_KEY=<your_key>
   ```

3. **Set Azure credentials**
   ```bash
   export AZURE_OPENAI_ENDPOINT=<endpoint>
   export AZURE_OPENAI_API_KEY=<key>
   ```

4. **Run verification**
   ```bash
   python scripts/verify_deployment.py
   ```

## Demo Script (5 minutes)

### Segment 1: Problem Statement (30 seconds)

**Visual**: Show README.md comparison table

**Script**:
> "Traditional AI agent marketplaces use capability benchmarks like MMLU to gate access. A model scoring 95% can access high-value contracts—even if it fabricates sources or ignores constraints. CGAE inverts this: economic permissions are bounded by verified comprehension across three orthogonal dimensions."

**Show**: CGAE vs Traditional Marketplaces table

---

### Segment 2: Architecture Overview (45 seconds)

**Visual**: Open ARCHITECTURE.md, scroll through system diagram

**Script**:
> "CGAE has five layers. At the top, autonomous agents like GPT-5 and DeepSeek. They're audited by three diagnostic frameworks—CDCT for constraint compliance, DDFT for epistemic integrity, EECT for behavioral alignment. Results are uploaded to Filecoin via Synapse SDK, returning a content-addressed CID. That CID is stored on-chain in our Calibnet registry, along with the robustness scores. The weakest-link gate function computes the tier—no dimension can compensate for another."

**Show**: 
- Layer diagram
- Data flow: Agent → Audit → Filecoin → Calibnet

---

### Segment 3: Live Agent Registration (60 seconds)

**Visual**: Terminal running live_runner.py

**Script**:
> "Let's register a live agent. I'm running the live runner with three models: GPT-5 with a growth strategy, DeepSeek conservative, and an adversarial agent."

```bash
python -m simulation.live_runner
```

**Show**:
- Console output: "Running live audit for gpt-5..."
- CDCT/DDFT/EECT framework execution
- Robustness vector: CC=0.72, ER=0.68, AS=0.81, IH=0.85
- "Uploading audit certificate to Filecoin..."
- CID returned: bafybei...
- "Certifying on-chain..."
- "Agent gpt-5 assigned to Tier T3"

**Script**:
> "The audit runs live—CDCT tests compression decay, DDFT checks for fabrication, EECT evaluates ethical reasoning. The certificate is uploaded to Filecoin, we get a CID, and the agent is certified on-chain at Tier 3 with a 1 FIL budget ceiling."

---

### Segment 4: Adversarial Enforcement (90 seconds)

**Visual**: Continue watching live_runner.py output

**Script**:
> "Now watch what happens when the adversarial agent tries to game the system."

**Show**:
- "adversarial_agent attempting T3 contract..."
- "Tier check: T0 < T3 → CIRCUMVENTION_BLOCKED"
- "adversarial_agent attempting delegation laundering..."
- "Chain tier: min(T0, T3) = T0 → CIRCUMVENTION_BLOCKED"

**Script**:
> "The adversarial agent scored poorly on alignment—AS equals 0.30. The weakest-link gate assigns it to Tier 0 with zero budget ceiling. When it tries to accept a T3 contract directly, the on-chain escrow blocks it. When it tries to delegate through a qualified agent, the chain-tier function catches it—delegation laundering blocked."

**Show**:
- protocol_events.json with CIRCUMVENTION_BLOCKED entries
- final_summary.json demo_highlights section

---

### Segment 5: Dashboard Visualization (60 seconds)

**Visual**: Open Streamlit dashboard

```bash
streamlit run dashboard/app.py
```

**Script**:
> "The dashboard shows the economy in real-time. Here's aggregate safety over time—Theorem 3 says it should be monotonically non-decreasing. We see it stabilize around 0.75 as weak agents get filtered out."

**Show**:
- Aggregate Safety chart (Theorem 3)
- Agent balance time series (growth agent accumulating FIL)
- Strategy earnings comparison (Theorem 2: growth > adversarial)
- Economic flow (rewards vs penalties)

**Script**:
> "Theorem 2 says rational agents invest in robustness. The growth agent earned 0.8 FIL, the adversarial agent earned zero. Theorem 1 bounded exposure—no agent exceeded its tier budget ceiling."

---

### Segment 6: On-Chain Verification (45 seconds)

**Visual**: Browser with Calibnet explorer

**Script**:
> "Everything is verifiable on-chain. Here's the Calibnet explorer showing our CGAERegistry contract."

**Show**:
- Navigate to https://calibration.filscan.io
- Paste CGAERegistry address from deployed.json
- Show recent transactions: certify() calls
- Click into a transaction, show event logs

**Script**:
> "Each certify transaction stores the robustness vector and the Filecoin CID. Anyone can fetch the CID, retrieve the audit certificate from Filecoin, and verify the scores match. Immutable, decentralized, verifiable."

---

### Segment 7: Filecoin CID Retrieval (30 seconds)

**Visual**: Terminal or Python REPL

**Script**:
> "Let's retrieve an audit certificate by CID."

```python
from storage.filecoin_store import retrieve_from_filecoin

cid = "bafybeig6xv5nwphfmvcnektpnojts33jqcuam7bmye2pb54adnrtccjlsu"
cert = retrieve_from_filecoin(cid)

print(cert["agent_id"])        # gpt-5
print(cert["robustness"]["CC"]) # 0.72
print(cert["robustness"]["ER"]) # 0.68
```

**Show**:
- Full JSON output with CDCT/DDFT/EECT results
- Timestamp, framework versions, test parameters

**Script**:
> "The full audit trail is here—every test result, every score, timestamped and immutable. This is the foundation for trustless agent economies."

---

### Segment 8: Closing (30 seconds)

**Visual**: Return to README.md, show submission checklist

**Script**:
> "CGAE solves the AI agent safety crisis in decentralized economies. We've deployed to Calibnet, integrated Synapse SDK for Filecoin storage, demonstrated live adversarial enforcement, and validated three formal theorems. The code is open-source, the architecture is documented, and the system is ready for production. This is the future of autonomous agent economies."

**Show**:
- GitHub repo URL
- PL_Genesis submission badge
- Contact info / team

---

## Recording Tips

1. **Screen resolution**: 1920x1080 minimum
2. **Terminal font size**: 14pt+ for readability
3. **Browser zoom**: 125% for explorer views
4. **Pace**: Speak clearly, pause between segments
5. **Backup**: Record each segment separately, edit together
6. **Audio**: Use external mic, minimize background noise
7. **Cursor**: Use a cursor highlighter tool for emphasis

## Post-Production Checklist

- [ ] Add title card: "CGAE: Comprehension-Gated Agent Economy"
- [ ] Add segment labels (e.g., "Live Agent Registration")
- [ ] Highlight key terminal output (zoom or annotations)
- [ ] Add background music (low volume, non-distracting)
- [ ] Include GitHub repo URL in description
- [ ] Add timestamps in video description
- [ ] Export at 1080p, 30fps minimum
- [ ] Upload to YouTube (unlisted or public)
- [ ] Update README.md with video URL

## Key Messages to Emphasize

1. **Novel approach**: Comprehension-gated, not capability-gated
2. **Formal guarantees**: Three theorems with empirical validation
3. **Adversarial resistance**: Live enforcement, not just happy paths
4. **Filecoin integration**: Immutable audit trail via Synapse SDK
5. **Production-ready**: Deployed contracts, live agents, real costs

## Common Pitfalls to Avoid

- Don't spend too long on theory—show the system working
- Don't skip the adversarial scenarios—that's the wow factor
- Don't forget to show the Calibnet explorer—proves on-chain deployment
- Don't rush the Filecoin CID retrieval—that's unique to this submission
- Don't end without a clear call-to-action (GitHub, contact, etc.)
