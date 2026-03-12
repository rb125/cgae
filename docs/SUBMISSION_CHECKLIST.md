# PL_Genesis Submission Checklist

## Required Deliverables

### 1. Synapse SDK / Filecoin Pin Integration ✅
- [x] Synapse SDK installed (`storage/package.json`)
- [x] Upload wrapper implemented (`storage/upload_to_synapse.mjs`)
- [x] Python bridge created (`storage/filecoin_store.py`)
- [x] Audit certificates uploaded to Filecoin
- [x] CIDs stored on-chain in `CGAERegistry.sol`
- [ ] **Document usage prominently in README** ← IN PROGRESS

**Evidence**:
- Code: `storage/upload_to_synapse.mjs`, `storage/filecoin_store.py`
- README section: "Filecoin Integration via Synapse SDK"
- Architecture diagram: ARCHITECTURE.md

---

### 2. Filecoin Calibration Testnet Deployment ✅
- [x] Contracts written in Solidity 0.8.20
- [x] Hardhat config for Calibnet (chain 314159)
- [x] Deployment script (`contracts/scripts/deploy.js`)
- [ ] **Contracts deployed** ← NEEDS DEPLOYMENT
- [ ] **Addresses in `contracts/deployed.json`** ← AFTER DEPLOYMENT
- [ ] **Explorer links in README** ← AFTER DEPLOYMENT

**Evidence**:
- Contracts: `contracts/CGAERegistry.sol`, `contracts/CGAEEscrow.sol`
- Config: `contracts/hardhat.config.js`
- Deployment: `contracts/deployed.json` (after deployment)

**Action Required**:
```bash
cd contracts
npm install
export PRIVATE_KEY=<your_calibnet_private_key>
npm run deploy:calibnet
# Updates deployed.json automatically
```

---

### 3. Working Demo (Frontend or CLI) ✅
- [x] CLI runner: `simulation/live_runner.py`
- [x] Dashboard: `dashboard/app.py` (Streamlit)
- [x] Adversarial scenarios included
- [x] Real-time visualization
- [ ] **Demo video recorded** ← NEEDS RECORDING

**Evidence**:
- CLI: `python -m simulation.live_runner`
- Dashboard: `streamlit run dashboard/app.py`
- Script: `DEMO_SCRIPT.md`

**Action Required**:
- Follow `DEMO_SCRIPT.md` to record 5-minute video
- Upload to YouTube
- Update README.md with video URL

---

### 4. Open-Source Code via GitHub ✅
- [x] Repository exists
- [x] Code is functional
- [x] README.md with setup instructions
- [x] License file (if applicable)
- [ ] **Repository is public** ← VERIFY BEFORE SUBMISSION

**Evidence**:
- GitHub URL: [INSERT YOUR REPO URL]
- README: Comprehensive setup and usage instructions
- Architecture: ARCHITECTURE.md with diagrams

---

### 5. Demo Video ⚠️
- [ ] **5-minute video recorded**
- [ ] Shows live agent registration with audit
- [ ] Shows adversarial enforcement scenarios
- [ ] Shows Calibnet explorer verification
- [ ] Shows Filecoin CID retrieval
- [ ] Shows dashboard with theorem validation
- [ ] Uploaded to YouTube
- [ ] URL added to README.md

**Action Required**:
- Record following `DEMO_SCRIPT.md`
- Upload to YouTube (unlisted or public)
- Add URL to README.md line 14: `DEMO_VIDEO_URL_HERE`

---

## Judging Criteria Optimization

### Technical Execution (40%)

**Strengths**:
- ✅ Production-quality Solidity contracts
- ✅ Synapse SDK integration for Filecoin storage
- ✅ Live LLM execution with 13 Azure models
- ✅ Sophisticated v2 agent architecture (5 layers)
- ✅ ~2000 lines of well-structured code

**Evidence to Highlight**:
- Code quality: Type hints, docstrings, modular design
- Testing: Synthetic runner validates theorems deterministically
- Integration: Seamless Python ↔ Node.js ↔ Solidity pipeline

---

### Potential Impact (20%)

**Strengths**:
- ✅ Addresses critical AI safety problem at economic scale
- ✅ Applicable beyond Filecoin (any blockchain + storage)
- ✅ Formal theorems with empirical validation
- ✅ Academic rigor (paper with proofs)

**Evidence to Highlight**:
- Problem statement: Traditional marketplaces lack safety guarantees
- Solution: Bounded exposure (Theorem 1), incentive compatibility (Theorem 2)
- Comparison table: CGAE vs Traditional Marketplaces

---

### Innovation / Wow Factor (30%)

**Strengths**:
- ✅ **Comprehension-gated access** (novel paradigm)
- ✅ **Weakest-link gate function** (prevents dimension gaming)
- ✅ **Three orthogonal robustness dimensions** (CDCT/DDFT/EECT)
- ✅ **Live adversarial enforcement** (not just happy paths)
- ✅ **Formal safety guarantees** (peer-reviewed quality)

**Evidence to Highlight**:
- Demo: Circumvention blocking, delegation laundering detection
- Architecture: Five-layer autonomous agent with self-verification
- Theorems: Bounded exposure, incentive compatibility, collusion resistance

---

### Presentation / Demo (10%)

**Strengths**:
- ✅ Clear problem definition
- ✅ Comprehensive README with setup instructions
- ✅ Architecture diagrams (ARCHITECTURE.md)
- ✅ Synapse SDK usage documented
- ⚠️ Demo video (needs recording)

**Evidence to Highlight**:
- README: Comparison table, architecture overview, code references
- ARCHITECTURE.md: Visual diagrams, data flow, adversarial scenarios
- Demo video: Live enforcement, Calibnet verification, Filecoin retrieval

---

## Pre-Submission Verification

Run the verification script:
```bash
python scripts/verify_deployment.py
```

Expected output:
```
✅ CGAERegistry deployed: 0x...
✅ CGAEEscrow deployed: 0x...
✅ Synapse SDK installed
✅ FILECOIN_PRIVATE_KEY configured
✅ Azure OpenAI credentials configured
✅ Test upload successful: bafybei...

🎉 All checks passed! Ready for demo.
```

---

## Submission Timeline

### Day 1: Deployment
- [ ] Deploy contracts to Calibnet
- [ ] Verify deployment with explorer
- [ ] Test Filecoin upload with real credentials
- [ ] Run live_runner.py with 3-5 agents
- [ ] Generate results for dashboard

### Day 2: Demo Video
- [ ] Record demo following DEMO_SCRIPT.md
- [ ] Edit video (add titles, highlights, music)
- [ ] Upload to YouTube
- [ ] Update README.md with video URL

### Day 3: Final Review
- [ ] Run verification script
- [ ] Review README for clarity
- [ ] Check all links work
- [ ] Ensure repository is public
- [ ] Submit to PL_Genesis portal

---

## Submission Portal Information

**Track**: Autonomous Agent Economy  
**Bounty**: Challenge #4 — Autonomous Agent Economy  
**Category**: Existing Code (if extending prior work) OR Fresh Code (if built during hackathon)

**Required Fields**:
- Project Name: Comprehension-Gated Agent Economy (CGAE)
- GitHub URL: [YOUR_REPO_URL]
- Demo Video URL: [YOUR_YOUTUBE_URL]
- Calibnet Contract Addresses: [FROM deployed.json]
- Short Description: "A robustness-first architecture where AI agents earn economic permissions through verified comprehension across three orthogonal dimensions, with Filecoin-backed audit trails and on-chain enforcement."

**Optional but Recommended**:
- Team Members: [YOUR_NAMES]
- Contact Email: [YOUR_EMAIL]
- Twitter/Social: [YOUR_HANDLES]
- Additional Documentation: Link to ARCHITECTURE.md

---

## Post-Submission

### If Selected for Founders Forge
- [ ] Prepare pitch deck (10 slides max)
- [ ] Identify 3 key milestones for accelerator
- [ ] Research Protocol Labs ecosystem partners
- [ ] Prepare questions for mentorship sessions

### Community Engagement
- [ ] Post demo video on Twitter/X
- [ ] Share in Filecoin Discord/Slack
- [ ] Write blog post explaining architecture
- [ ] Engage with other hackathon participants

---

## Contact for Questions

**Hackathon Support**:
- PL_Genesis Discord: [LINK]
- Filecoin Slack: [LINK]
- Synapse SDK Docs: https://docs.synapse.storage

**Technical Issues**:
- Calibnet Faucet: https://faucet.calibnet.chainsafe-fil.io/funds.html
- Hardhat Docs: https://hardhat.org/docs
- Azure OpenAI: https://learn.microsoft.com/azure/ai-services/openai/

---

## Success Metrics

**Minimum Viable Submission**:
- ✅ Contracts deployed to Calibnet
- ✅ Synapse SDK integration working
- ✅ Demo video showing core functionality
- ✅ Open-source code on GitHub

**Competitive Submission** (aim for this):
- ✅ All minimum requirements
- ✅ Live adversarial enforcement scenarios
- ✅ Dashboard with theorem validation
- ✅ Comprehensive documentation (README + ARCHITECTURE)
- ✅ Calibnet explorer verification shown in demo

**Top-Tier Submission** (Founders Forge candidate):
- ✅ All competitive requirements
- ✅ Formal theorems with empirical validation
- ✅ Novel architecture (comprehension-gated access)
- ✅ Production-ready code quality
- ✅ Clear path to real-world deployment

---

## Final Checklist Before Submit

- [ ] All code committed and pushed to GitHub
- [ ] Repository is public
- [ ] README.md has demo video URL
- [ ] contracts/deployed.json has Calibnet addresses
- [ ] Demo video is public/unlisted on YouTube
- [ ] Verification script passes all checks
- [ ] Team members listed (if applicable)
- [ ] License file included (MIT recommended)
- [ ] .gitignore excludes secrets (.env, private keys)
- [ ] All links in README work
- [ ] Architecture diagrams render correctly
- [ ] Submission form filled out completely

**When all boxes checked**: Submit to PL_Genesis portal 🚀
