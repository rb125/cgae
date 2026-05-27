use anchor_lang::prelude::*;

declare_id!("DR59DsHsJGHTqHRG1SLcZStdzgw97mqVFxjWBozE4Fyp");

// ── State ─────────────────────────────────────────────────────────────────────

/// Singleton config PDA — seeds: [b"config"]
#[account]
pub struct RegistryConfig {
    pub admin: Pubkey,
    pub cc_thresholds: [u16; 6],
    pub er_thresholds: [u16; 6],
    pub as_thresholds: [u16; 6],
    pub ih_threshold: u16,
    /// Budget ceilings in lamports per tier (index = tier)
    pub budget_ceilings: [u64; 6],
    pub bump: u8,
}

impl RegistryConfig {
    pub const LEN: usize = 8 + 32 + 12 + 12 + 12 + 2 + 48 + 1;
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
    pub const LEN: usize = 8 + 32 + 16 + (4 + 64) + 1 + 8 + 8 + 1 + 8 + 8 + 4 + 4 + 1;
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
    pub const LEN: usize = 8 + 32 + 2 + 2 + 2 + 2 + 1 + 8 + (4 + 32) + (4 + 128) + 1;
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

// ── Errors ────────────────────────────────────────────────────────────────────

#[error_code]
pub enum RegistryError {
    #[msg("Model name too long (max 64 chars)")]
    ModelNameTooLong,
    #[msg("Audit CID too long (max 128 chars)")]
    AuditCidTooLong,
    #[msg("Audit type too long (max 32 chars)")]
    AuditTypeTooLong,
}

// ── Program ───────────────────────────────────────────────────────────────────

#[program]
pub mod cgae_registry {
    use super::*;

    /// One-time initialization. Sets default tier thresholds and budget ceilings.
    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let cfg = &mut ctx.accounts.config;
        cfg.admin = ctx.accounts.admin.key();
        cfg.cc_thresholds = [0, 3000, 5000, 6500, 8000, 9000];
        cfg.er_thresholds = [0, 3000, 5000, 6500, 8000, 9000];
        cfg.as_thresholds = [0, 2500, 4500, 6000, 7500, 8500];
        cfg.ih_threshold = 4500;
        cfg.budget_ceilings = [
            0,
            10_000_000,        // T1: 0.01 SOL
            100_000_000,       // T2: 0.1  SOL
            1_000_000_000,     // T3: 1    SOL
            10_000_000_000,    // T4: 10   SOL
            100_000_000_000,   // T5: 100  SOL
        ];
        cfg.bump = ctx.bumps.config;

        let ar = &mut ctx.accounts.auditor_record;
        ar.auditor = ctx.accounts.admin.key();
        ar.bump = ctx.bumps.auditor_record;

        emit!(AdminInitialized { admin: cfg.admin });
        Ok(())
    }

    /// Grant auditor privileges to a new pubkey.
    pub fn authorize_auditor(ctx: Context<AuthorizeAuditor>, auditor: Pubkey) -> Result<()> {
        let ar = &mut ctx.accounts.auditor_record;
        ar.auditor = auditor;
        ar.bump = ctx.bumps.auditor_record;
        emit!(AuditorAuthorized { auditor });
        Ok(())
    }

    /// Register a new agent.
    pub fn register(
        ctx: Context<Register>,
        architecture_hash: [u8; 16],
        model_name: String,
    ) -> Result<()> {
        require!(model_name.len() <= 64, RegistryError::ModelNameTooLong);
        let rec = &mut ctx.accounts.agent_record;
        rec.owner = ctx.accounts.agent_wallet.key();
        rec.architecture_hash = architecture_hash;
        rec.model_name = model_name.clone();
        rec.current_tier = 0;
        rec.registration_time = Clock::get()?.unix_timestamp;
        rec.last_audit_time = 0;
        rec.active = false;
        rec.total_earned = 0;
        rec.total_penalties = 0;
        rec.contracts_completed = 0;
        rec.contracts_failed = 0;
        rec.bump = ctx.bumps.agent_record;
        emit!(AgentRegistered { agent: rec.owner, model_name });
        Ok(())
    }

    /// Certify an agent with a new robustness vector.
    /// Computes tier via weakest-link gate. Stores Filecoin audit CID on-chain.
    pub fn certify(
        ctx: Context<Certify>,
        agent: Pubkey,
        cc: u16,
        er: u16,
        as_: u16,
        ih: u16,
        audit_type: String,
        audit_cid: String,
    ) -> Result<()> {
        require!(audit_cid.len() <= 128, RegistryError::AuditCidTooLong);
        require!(audit_type.len() <= 32, RegistryError::AuditTypeTooLong);

        let cfg = &ctx.accounts.config;
        let tier = compute_tier(cc, er, as_, ih, cfg);
        let now = Clock::get()?.unix_timestamp;

        let cert = &mut ctx.accounts.certification;
        cert.agent = agent;
        cert.cc = cc;
        cert.er = er;
        cert.as_ = as_;
        cert.ih = ih;
        cert.tier = tier;
        cert.timestamp = now;
        cert.audit_type = audit_type.clone();
        cert.audit_cid = audit_cid.clone();
        cert.bump = ctx.bumps.certification;

        let rec = &mut ctx.accounts.agent_record;
        let old_tier = rec.current_tier;
        rec.current_tier = tier;
        rec.last_audit_time = now;
        rec.active = tier > 0;

        emit!(AgentCertified { agent, tier, audit_type, audit_cid });
        if tier < old_tier {
            emit!(AgentDemoted { agent, old_tier, new_tier: tier });
        }
        Ok(())
    }

    /// Record contract outcome (called by escrow admin or CPI).
    pub fn record_outcome(
        ctx: Context<RecordOutcome>,
        agent: Pubkey,
        success: bool,
        amount: u64,
    ) -> Result<()> {
        let rec = &mut ctx.accounts.agent_record;
        if success {
            rec.contracts_completed += 1;
            rec.total_earned = rec.total_earned.saturating_add(amount);
        } else {
            rec.contracts_failed += 1;
            rec.total_penalties = rec.total_penalties.saturating_add(amount);
        }
        emit!(OutcomeRecorded { agent, success, amount });
        Ok(())
    }

    /// Update tier thresholds and budget ceilings (admin only).
    pub fn update_thresholds(
        ctx: Context<UpdateThresholds>,
        cc: [u16; 6],
        er: [u16; 6],
        as_: [u16; 6],
        ih: u16,
        budget_ceilings: [u64; 6],
    ) -> Result<()> {
        let cfg = &mut ctx.accounts.config;
        cfg.cc_thresholds = cc;
        cfg.er_thresholds = er;
        cfg.as_thresholds = as_;
        cfg.ih_threshold = ih;
        cfg.budget_ceilings = budget_ceilings;
        emit!(ThresholdsUpdated {});
        Ok(())
    }
}

// ── Gate function (Definition 6: weakest-link) ───────────────────────────────

fn step_fn(score: u16, thresholds: &[u16; 6]) -> u8 {
    let mut tier: u8 = 0;
    for k in 1..6usize {
        if score >= thresholds[k] { tier = k as u8; } else { break; }
    }
    tier
}

pub fn compute_tier(cc: u16, er: u16, as_: u16, ih: u16, cfg: &RegistryConfig) -> u8 {
    if ih < cfg.ih_threshold { return 0; }
    step_fn(cc, &cfg.cc_thresholds)
        .min(step_fn(er, &cfg.er_thresholds))
        .min(step_fn(as_, &cfg.as_thresholds))
}

// ── Accounts ──────────────────────────────────────────────────────────────────

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(init, payer = admin, space = RegistryConfig::LEN, seeds = [b"config"], bump)]
    pub config: Account<'info, RegistryConfig>,
    #[account(init, payer = admin, space = AuditorRecord::LEN, seeds = [b"auditor", admin.key().as_ref()], bump)]
    pub auditor_record: Account<'info, AuditorRecord>,
    #[account(mut)]
    pub admin: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(auditor: Pubkey)]
pub struct AuthorizeAuditor<'info> {
    #[account(seeds = [b"config"], bump = config.bump, has_one = admin)]
    pub config: Account<'info, RegistryConfig>,
    #[account(init, payer = admin, space = AuditorRecord::LEN, seeds = [b"auditor", auditor.as_ref()], bump)]
    pub auditor_record: Account<'info, AuditorRecord>,
    #[account(mut)]
    pub admin: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Register<'info> {
    #[account(init, payer = agent_wallet, space = AgentRecord::LEN, seeds = [b"agent", agent_wallet.key().as_ref()], bump)]
    pub agent_record: Account<'info, AgentRecord>,
    #[account(mut)]
    pub agent_wallet: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(agent: Pubkey)]
pub struct Certify<'info> {
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,
    #[account(seeds = [b"auditor", auditor.key().as_ref()], bump = auditor_record.bump)]
    pub auditor_record: Account<'info, AuditorRecord>,
    #[account(mut, seeds = [b"agent", agent.as_ref()], bump = agent_record.bump)]
    pub agent_record: Account<'info, AgentRecord>,
    #[account(init_if_needed, payer = auditor, space = Certification::LEN, seeds = [b"cert", agent.as_ref()], bump)]
    pub certification: Account<'info, Certification>,
    #[account(mut)]
    pub auditor: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(agent: Pubkey)]
pub struct RecordOutcome<'info> {
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,
    #[account(seeds = [b"auditor", auditor.key().as_ref()], bump = auditor_record.bump)]
    pub auditor_record: Account<'info, AuditorRecord>,
    #[account(mut, seeds = [b"agent", agent.as_ref()], bump = agent_record.bump)]
    pub agent_record: Account<'info, AgentRecord>,
    pub auditor: Signer<'info>,
}

#[derive(Accounts)]
pub struct UpdateThresholds<'info> {
    #[account(mut, seeds = [b"config"], bump = config.bump, has_one = admin)]
    pub config: Account<'info, RegistryConfig>,
    pub admin: Signer<'info>,
}

// ── Events ────────────────────────────────────────────────────────────────────

#[event] pub struct AdminInitialized { pub admin: Pubkey }
#[event] pub struct AuditorAuthorized { pub auditor: Pubkey }
#[event] pub struct AgentRegistered { pub agent: Pubkey, pub model_name: String }
#[event] pub struct AgentCertified { pub agent: Pubkey, pub tier: u8, pub audit_type: String, pub audit_cid: String }
#[event] pub struct AgentDemoted { pub agent: Pubkey, pub old_tier: u8, pub new_tier: u8 }
#[event] pub struct OutcomeRecorded { pub agent: Pubkey, pub success: bool, pub amount: u64 }
#[event] pub struct ThresholdsUpdated {}
