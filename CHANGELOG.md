# CGAE Changelog

## [Solana Migration] — 2026-04-10

### Context
CGAE was originally built for Filecoin Calibnet (EVM/Solidity). This migration adapts the on-chain layer to Solana while **keeping Filecoin for verifiable audit storage** — Filecoin CIDs are now anchored on Solana instead of on the EVM chain.

Cross-chain pitch: Solana handles economic logic (fast, cheap on-chain state); Filecoin handles verifiable storage (audit proofs). Anyone can verify agent credentials by fetching the CID from the Solana `Certification` PDA and retrieving the JSON from Filecoin.

---

### Added: `solana_contracts/` — Anchor workspace

Replaces `contracts/` (Hardhat/Solidity). Two Anchor programs written in Rust targeting Solana devnet.

#### `programs/cgae_registry` — replaces `CGAERegistry.sol`

| Instruction | Reason |
|---|---|
| `initialize` | One-time setup: tier thresholds, budget ceilings (in lamports), admin as first auditor |
| `register` | Agent self-registers; creates `AgentRecord` PDA (`[b"agent", wallet]`) |
| `certify` | Auditor submits robustness scores + **Filecoin audit CID** → weakest-link gate computes tier → stored in `Certification` PDA (`[b"cert", wallet]`) |
| `record_outcome` | Tracks earned/penalties per agent (called by escrow admin) |
| `authorize_auditor` | Admin grants auditor privileges; creates `AuditorRecord` PDA |
| `update_thresholds` | Admin updates tier thresholds and budget ceilings |

Key design decisions:
- Filecoin CID preserved as `audit_cid: String` field in `Certification` PDA — cross-chain story intact
- Weakest-link gate function (`compute_tier`) ported from `cgae_engine/gate.py` directly into Rust
- Budget ceilings in lamports: T1=0.01 SOL, T2=0.1, T3=1, T4=10, T5=100

#### `programs/cgae_escrow` — replaces `CGAEEscrow.sol`

| Instruction | Reason |
|---|---|
| `initialize` | Sets admin and registry program ID |
| `create_contract` | Issuer transfers SOL reward into contract PDA (`[b"contract", issuer, nonce]`) |
| `accept_contract` | Agent deposits penalty collateral; enforces tier ≥ min_tier and exposure ≤ budget ceiling (Theorem 1) |
| `complete_contract` | Admin releases reward + collateral to agent on success |
| `fail_contract` | Admin forfeits penalty, returns reward to issuer on failure |
| `expire_contract` | Anyone can expire open contracts past deadline; reward returned to issuer |

Key design decisions:
- Budget ceiling check reads `RegistryConfig` account bytes directly (fixed byte offsets) — avoids cross-program CPI complexity while keeping the enforcement on-chain
- SOL lamport transfers replace FIL wei transfers
- `ContractStatus` enum replaces Solidity enum
- PDAs replace Solidity mappings throughout

#### Solana account layout (PDA seeds)

| Account | Seeds | Replaces |
|---|---|---|
| `RegistryConfig` | `[b"config"]` | `admin`, `thresholds`, `budgetCeilings` state vars |
| `AgentRecord` | `[b"agent", wallet]` | `agents` mapping |
| `Certification` | `[b"cert", wallet]` | `currentCertifications` mapping |
| `AuditorRecord` | `[b"auditor", wallet]` | `authorizedAuditors` mapping |
| `EscrowState` | `[b"escrow_state"]` | global accounting vars |
| `EconomicContract` | `[b"contract", issuer, nonce]` | `contracts` mapping |

---

### Pending

- [ ] Update Python engine (`cgae_engine/contracts.py`, `registry.py`, `economy.py`) to interact with Solana programs via `solders` / `anchorpy`
- [ ] Replace FIL currency references with SOL/lamports in simulation engine
- [ ] Update `storage/filecoin_store.py` to write CID to Solana `Certification` PDA instead of EVM `CGAERegistry.certify()`
- [ ] Deploy to Solana devnet; update `contracts/deployed.json` equivalent for Solana program IDs
- [ ] Update dashboard to reflect SOL balances

---

## [Python Engine — Solana currency + storage updates] — 2026-04-10

### `cgae_engine/economy.py`
- Renamed currency comments: `FIL` → `SOL` in `initial_balance`, `audit_cost`, `storage_cost_per_step`
- `test_fil_top_up_*` field names kept for back-compat with existing runner configs; comment updated to say "SOL top-ups"

### `cgae_engine/registry.py`
- `AgentRecord.balance` comment: `FIL` → `SOL`
- `audit_cid` property docstring updated: CID is now anchored on Solana `Certification` PDA, not EVM

### `storage/filecoin_store.py`
- Module docstring updated: removed EVM `CGAERegistry.certify()` reference; Solana is now the canonical on-chain registry. Filecoin remains for audit storage only.
- Added `FilecoinStore.anchor_cid_on_solana()` — writes the Filecoin CID into the agent's `Certification` PDA on Solana via the `cgae_registry` program's `certify` instruction. Invokes `storage/anchor_certify.mjs`. Gracefully no-ops if `SOLANA_PRIVATE_KEY` is unset or the script is absent.
- `store_audit_json()` gains optional `solana_anchor` dict param — when provided, calls `anchor_cid_on_solana()` after upload. Fully backward-compatible (defaults to `None`).

### Pending

- [ ] Write `storage/anchor_certify.mjs` — Node.js Anchor client that calls `cgae_registry.certify()` on Solana devnet
- [ ] Deploy programs to Solana devnet; record program IDs in `solana_contracts/deployed.json`
- [ ] Update `live_runner.py` to pass `solana_anchor` dict to `store_audit_json`
- [ ] Update dashboard to reflect SOL balances

---

## [storage/anchor_certify.mjs] — 2026-04-10

### Added
New Node.js script that calls `cgae_registry.certify()` on Solana to anchor a Filecoin audit CID in the agent's `Certification` PDA.

**How it works:**
1. Reads a JSON payload file (agent pubkey, robustness scores u16, audit_type, audit_cid, rpc_url)
2. Loads the payer keypair from `SOLANA_PRIVATE_KEY` env var (base58 string or path to keypair JSON)
3. Derives all required PDAs: `config`, `auditor`, `agent_record`, `cert`
4. Encodes the `certify` instruction with Anchor discriminator (`sha256("global:certify")[0:8]`) + borsh-serialized args
5. Sends and confirms the transaction; outputs `{ ok: true, signature: "..." }`

**Dependencies:** Uses `@solana/web3.js` and `@anchor-lang/borsh` from `solana_contracts/node_modules/` — no extra `npm install` needed.

**Called by:** `FilecoinStore.anchor_cid_on_solana()` in `storage/filecoin_store.py` via subprocess.

---

## [server/live_runner.py — Solana currency + CID anchoring] — 2026-04-10

### Currency rename
- `USD_TO_FIL` → `USD_TO_SOL`, `compute_token_cost_fil` → `compute_token_cost_sol`, `total_token_cost_fil` → `total_token_cost_sol`
- All log strings, print statements, and JSON output keys updated from `FIL` → `SOL`

### Solana CID anchoring
- After `audit_agent()` in `setup()`, calls `FilecoinStore().anchor_cid_on_solana()` to write the Filecoin audit CID into the agent's `Certification` PDA on Solana
- Keyed by `SOLANA_AGENT_PUBKEY_<MODEL_NAME>` env var per agent — no-op if unset
- `FilecoinStore` imported from `storage.filecoin_store`

### Pending
- [ ] Deploy programs to Solana devnet (`anchor build && anchor deploy --provider.cluster devnet`)
- [ ] Write `solana_contracts/deployed.json` with live program IDs
- [ ] Update dashboard currency labels (FIL → SOL)

---

## [dashboard/app.py — Crypto UI redesign + SOL migration] — 2026-04-10

### Full UI/UX redesign
Replaced the light Streamlit theme with a dark crypto dashboard aesthetic:
- **Color scheme:** `#0a0f1e` background, Solana purple (`#8b5cf6`) + Solana green (`#14f195`) accents, glassmorphism cards
- **Typography:** Inter + IBM Plex Mono for numbers/addresses
- **Animated loading spinner** while economy initializes
- **Custom HTML stat cards** with monospace values and colored accents
- **Section dividers** with uppercase labels and subtle borders
- **Plotly dark theme** with transparent backgrounds and subtle grid lines

### New tab structure
| Tab | Content |
|---|---|
| ◎ Overview | KPI row, live event feed, safety chart, balance + contract flow, strategy earnings |
| ⬡ Agents | Leaderboard with tier badges, robustness radar chart, tier donut |
| ⚡ Tasks | Pass/fail metrics, task execution feed with Filecoin CID display |
| 🔗 On-Chain | Deployed program addresses (Solana-first), cross-chain architecture diagram, gate thresholds |

### Currency
- All `FIL` → `SOL` in labels, chart axes, and metric values
- `load_deployed()` tries `solana_contracts/deployed.json` first, falls back to `contracts/deployed.json`

### `hf_backend/dashboard.html`
- All `FIL` currency labels updated to `SOL`

---

## [Deployment — Solana Devnet] — 2026-04-10

### Programs deployed to Solana Devnet

| Program | ID |
|---|---|
| `cgae_registry` | `DR59DsHsJGHTqHRG1SLcZStdzgw97mqVFxjWBozE4Fyp` |
| `cgae_escrow` | `FhQDQVpwPZDAEd7HU4WmZBkwe7P8wtdg83tYr4h1FPUe` |

- IDL metadata accounts written on-chain
- `solana_contracts/deployed.json` created with program IDs, cluster, explorer URL
- Deployer: `5VGdPCpthqfUFWqXjQpH7nhmJmeEM6hh4x3uk3o9qcLb`
- Explorer: https://explorer.solana.com/?cluster=devnet

### Build fix
- Removed stale `tests/test_initialize.rs` from both programs (referenced old `solana_contracts` crate name, blocked `anchor build` IDL generation)
