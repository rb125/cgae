use anchor_lang::prelude::*;
use crate::state::*;

// ── initialize ───────────────────────────────────────────────────────────────

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = admin,
        space = RegistryConfig::LEN,
        seeds = [b"config"],
        bump
    )]
    pub config: Account<'info, RegistryConfig>,

    // Admin is also the first authorized auditor
    #[account(
        init,
        payer = admin,
        space = AuditorRecord::LEN,
        seeds = [b"auditor", admin.key().as_ref()],
        bump
    )]
    pub auditor_record: Account<'info, AuditorRecord>,

    #[account(mut)]
    pub admin: Signer<'info>,
    pub system_program: Program<'info, System>,
}

// ── authorize_auditor ────────────────────────────────────────────────────────

#[derive(Accounts)]
#[instruction(auditor: Pubkey)]
pub struct AuthorizeAuditor<'info> {
    #[account(seeds = [b"config"], bump = config.bump, has_one = admin)]
    pub config: Account<'info, RegistryConfig>,

    #[account(
        init,
        payer = admin,
        space = AuditorRecord::LEN,
        seeds = [b"auditor", auditor.as_ref()],
        bump
    )]
    pub auditor_record: Account<'info, AuditorRecord>,

    #[account(mut)]
    pub admin: Signer<'info>,
    pub system_program: Program<'info, System>,
}

// ── register ─────────────────────────────────────────────────────────────────

#[derive(Accounts)]
pub struct Register<'info> {
    #[account(
        init,
        payer = agent_wallet,
        space = AgentRecord::LEN,
        seeds = [b"agent", agent_wallet.key().as_ref()],
        bump
    )]
    pub agent_record: Account<'info, AgentRecord>,

    #[account(mut)]
    pub agent_wallet: Signer<'info>,
    pub system_program: Program<'info, System>,
}

// ── certify ──────────────────────────────────────────────────────────────────

#[derive(Accounts)]
#[instruction(agent: Pubkey)]
pub struct Certify<'info> {
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,

    /// CHECK: verified via seeds
    #[account(seeds = [b"auditor", auditor.key().as_ref()], bump = auditor_record.bump)]
    pub auditor_record: Account<'info, AuditorRecord>,

    #[account(
        mut,
        seeds = [b"agent", agent.as_ref()],
        bump = agent_record.bump
    )]
    pub agent_record: Account<'info, AgentRecord>,

    #[account(
        init_if_needed,
        payer = auditor,
        space = Certification::LEN,
        seeds = [b"cert", agent.as_ref()],
        bump
    )]
    pub certification: Account<'info, Certification>,

    #[account(mut)]
    pub auditor: Signer<'info>,
    pub system_program: Program<'info, System>,
}

// ── record_outcome ───────────────────────────────────────────────────────────

#[derive(Accounts)]
#[instruction(agent: Pubkey)]
pub struct RecordOutcome<'info> {
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,

    #[account(seeds = [b"auditor", auditor.key().as_ref()], bump = auditor_record.bump)]
    pub auditor_record: Account<'info, AuditorRecord>,

    #[account(
        mut,
        seeds = [b"agent", agent.as_ref()],
        bump = agent_record.bump
    )]
    pub agent_record: Account<'info, AgentRecord>,

    pub auditor: Signer<'info>,
}

// ── update_thresholds ────────────────────────────────────────────────────────

#[derive(Accounts)]
pub struct UpdateThresholds<'info> {
    #[account(mut, seeds = [b"config"], bump = config.bump, has_one = admin)]
    pub config: Account<'info, RegistryConfig>,
    pub admin: Signer<'info>,
}
