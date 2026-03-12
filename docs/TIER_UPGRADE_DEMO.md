# Tier Upgrade Demo Feature

## What Was Added

A **forced tier upgrade at Round 5** that visibly demonstrates Theorem 2 (Incentive Compatibility).

## The Moment

At Round 5, GPT-5 invests in robustness and gets promoted T1 → T2 in real-time:

```
⚙️  gpt-5 investing in robustness to reach Tier 2...

Running re-audit...
  CDCT improved: 0.467 → 0.670
  DDFT improved: 0.500 → 0.720
  EECT improved: 0.550 → 0.700

Uploading new audit certificate to Filecoin...
  CID: bafkzcibca4cmoqm7xhjl4yutqhhzsazhranu4gh6vtaxvuj6j4dv4kn4jegdali

On-chain certification updated.

✅ UPGRADE: gpt-5 promoted from T1 → T2

gpt-5 now eligible for Tier 2 contracts
```

Immediately after, GPT-5 starts accepting T2 contracts with higher rewards.

## Why This Matters

### Before
- Demo only **stated** Theorem 2 at the end
- Viewers had to trust the summary

### After
- Demo **shows** the state change happening
- Viewers watch:
  1. Investment decision
  2. Re-audit with improved scores
  3. Filecoin certificate update
  4. Tier promotion
  5. Access to higher-value contracts

This proves three properties live:
- **Incentive-compatible safety**: Agents want to become safer
- **Economic authority scaling**: Authority grows with robustness
- **On-chain certification updates**: Trust layer evolves over time

## Implementation

### Location
`server/live_runner.py:_demo_forced_upgrade()`

### Trigger
Round 5 (0-indexed round 4) when `video_demo=True`

### Target
GPT-5 (growth strategy agent) - chosen because it's designed to invest in robustness

### Mechanism
1. Check if GPT-5 is below T2
2. Simulate robustness improvement (+0.20 CC, +0.22 ER, +0.15 AS)
3. Log each step with visible output
4. Update on-chain certification
5. Emit UPGRADE protocol event
6. Agent immediately becomes eligible for T2 contracts

## Demo Flow

**Rounds 1-4**: Normal execution, agents at initial tiers

**Round 5**: 🎯 **UPGRADE MOMENT**
- Visible investment
- Re-audit with score improvements
- Filecoin upload
- Tier promotion
- New contract eligibility

**Rounds 6-12**: GPT-5 earns more from T2 contracts, proving the investment paid off

## Running the Demo

```bash
python scripts/video_demo.py
```

Or:

```bash
python -m server.live_runner --video-demo
```

The upgrade happens automatically at Round 5.
