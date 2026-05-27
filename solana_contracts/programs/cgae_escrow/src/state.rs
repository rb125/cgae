use anchor_lang::prelude::*;

#[derive(AnchorSerialize, AnchorDeserialize, Clone, PartialEq, Eq)]
pub enum ContractStatus {
    Open,
    Assigned,
    Completed,
    Failed,
    Expired,
}

/// Per-contract PDA — seeds: [b"contract", issuer, nonce_bytes]
#[account]
pub struct EconomicContract {
    pub contract_id: [u8; 32],
    pub issuer: Pubkey,
    pub assigned_agent: Pubkey,   // Pubkey::default() when unassigned
    pub constraints_hash: [u8; 32],
    pub verifier_spec_cid: String, // max 128 bytes
    pub domain: String,            // max 32 bytes
    pub min_tier: u8,
    pub reward: u64,               // lamports, held in PDA
    pub penalty: u64,              // lamports, deposited by agent on accept
    pub deadline: i64,
    pub created_at: i64,
    pub status: ContractStatus,
    pub bump: u8,
}

impl EconomicContract {
    pub const LEN: usize = 8
        + 32          // contract_id
        + 32          // issuer
        + 32          // assigned_agent
        + 32          // constraints_hash
        + 4 + 128     // verifier_spec_cid
        + 4 + 32      // domain
        + 1           // min_tier
        + 8           // reward
        + 8           // penalty
        + 8           // deadline
        + 8           // created_at
        + 1           // status (enum)
        + 1;          // bump
}

/// Global escrow stats PDA — seeds: [b"escrow_state"]
#[account]
pub struct EscrowState {
    pub admin: Pubkey,
    pub registry_program: Pubkey,
    pub total_rewards_paid: u64,
    pub total_penalties_collected: u64,
    pub contract_count: u64,
    pub bump: u8,
}

impl EscrowState {
    pub const LEN: usize = 8 + 32 + 32 + 8 + 8 + 8 + 1;
}
