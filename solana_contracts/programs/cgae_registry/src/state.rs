use anchor_lang::prelude::*;

// ── Account data structures ──────────────────────────────────────────────────

/// Singleton config PDA — seeds: [b"config"]
#[account]
pub struct RegistryConfig {
    pub admin: Pubkey,
    /// Tier thresholds scaled by 10_000. Index = tier (0-5).
    pub cc_thresholds: [u16; 6],
    pub er_thresholds: [u16; 6],
    pub as_thresholds: [u16; 6],
    /// IH below this → forced T0
    pub ih_threshold: u16,
    /// Budget ceilings in lamports per tier
    pub budget_ceilings: [u64; 6],
    pub bump: u8,
}

impl RegistryConfig {
    pub const LEN: usize = 8
        + 32          // admin
        + 6 * 2       // cc_thresholds
        + 6 * 2       // er_thresholds
        + 6 * 2       // as_thresholds
        + 2           // ih_threshold
        + 6 * 8       // budget_ceilings
        + 1;          // bump
}

/// Per-agent PDA — seeds: [b"agent", agent_wallet]
#[account]
pub struct AgentRecord {
    pub owner: Pubkey,
    pub architecture_hash: [u8; 16],
    pub model_name: String,        // max 64 bytes
    pub current_tier: u8,
    pub registration_time: i64,
    pub last_audit_time: i64,
    pub active: bool,
    pub total_earned: u64,
    pub total_penalties: u64,
    pub contracts_completed: u32,
    pub contracts_failed: u32,
    pub bump: u8,
}

impl AgentRecord {
    pub const LEN: usize = 8
        + 32          // owner
        + 16          // architecture_hash
        + 4 + 64      // model_name (string prefix + max bytes)
        + 1           // current_tier
        + 8           // registration_time
        + 8           // last_audit_time
        + 1           // active
        + 8           // total_earned
        + 8           // total_penalties
        + 4           // contracts_completed
        + 4           // contracts_failed
        + 1;          // bump
}

/// Per-agent current certification PDA — seeds: [b"cert", agent_wallet]
#[account]
pub struct Certification {
    pub agent: Pubkey,
    pub cc: u16,
    pub er: u16,
    pub as_: u16,
    pub ih: u16,
    pub tier: u8,
    pub timestamp: i64,
    pub audit_type: String,   // max 32 bytes
    pub audit_cid: String,    // max 128 bytes (Filecoin CID)
    pub bump: u8,
}

impl Certification {
    pub const LEN: usize = 8
        + 32          // agent
        + 2 + 2 + 2 + 2  // cc, er, as_, ih
        + 1           // tier
        + 8           // timestamp
        + 4 + 32      // audit_type
        + 4 + 128     // audit_cid
        + 1;          // bump
}

/// Authorized auditor PDA — seeds: [b"auditor", auditor_wallet]
#[account]
pub struct AuditorRecord {
    pub auditor: Pubkey,
    pub bump: u8,
}

impl AuditorRecord {
    pub const LEN: usize = 8 + 32 + 1;
}
