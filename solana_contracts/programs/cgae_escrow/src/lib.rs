use anchor_lang::prelude::*;
use anchor_lang::system_program;

declare_id!("FhQDQVpwPZDAEd7HU4WmZBkwe7P8wtdg83tYr4h1FPUe");

// ── State ─────────────────────────────────────────────────────────────────────

#[derive(AnchorSerialize, AnchorDeserialize, Clone, PartialEq, Eq)]
pub enum ContractStatus { Open, Assigned, Completed, Failed, Expired }

/// Per-contract PDA — seeds: [b"contract", issuer, nonce_le_bytes]
#[account]
pub struct EconomicContract {
    pub contract_id: [u8; 32],
    pub issuer: Pubkey,
    pub assigned_agent: Pubkey,
    pub constraints_hash: [u8; 32],
    pub verifier_spec_cid: String,  // max 128
    pub domain: String,             // max 32
    pub min_tier: u8,
    pub reward: u64,
    pub penalty: u64,
    pub deadline: i64,
    pub created_at: i64,
    pub status: ContractStatus,
    pub bump: u8,
}

impl EconomicContract {
    pub const LEN: usize = 8 + 32 + 32 + 32 + 32 + (4+128) + (4+32) + 1 + 8 + 8 + 8 + 8 + 1 + 1;
}

/// Global stats PDA — seeds: [b"escrow_state"]
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

// ── Errors ────────────────────────────────────────────────────────────────────

#[error_code]
pub enum EscrowError {
    #[msg("Contract is not open")]           NotOpen,
    #[msg("Contract is not assigned")]       NotAssigned,
    #[msg("Deadline has passed")]            DeadlinePassed,
    #[msg("Contract has not expired yet")]   NotExpired,
    #[msg("Agent is not active")]            AgentNotActive,
    #[msg("Agent tier too low")]             TierTooLow,
    #[msg("Would exceed budget ceiling")]    BudgetCeilingExceeded,
    #[msg("Reward must be > 0")]             ZeroReward,
    #[msg("Invalid min tier (1-5)")]         InvalidTier,
    #[msg("Verifier spec CID too long")]     VerifierCidTooLong,
    #[msg("Domain too long")]                DomainTooLong,
    #[msg("Recipient mismatch")]             RecipientMismatch,
    #[msg("Issuer mismatch")]                IssuerMismatch,
}

// ── AgentRecord / RegistryConfig byte offsets for direct account reads ────────
// These mirror the serialized layout of cgae_registry accounts.
// AgentRecord (after 8-byte discriminator):
//   owner[32] arch_hash[16] model_name[4+64] current_tier[1] reg_time[8] last_audit[8] active[1]
const AGENT_TIER_OFFSET: usize   = 8 + 32 + 16 + 4 + 64;       // = 124
const AGENT_ACTIVE_OFFSET: usize = AGENT_TIER_OFFSET + 1 + 8 + 8; // = 141

// RegistryConfig (after 8-byte discriminator):
//   admin[32] cc[12] er[12] as[12] ih[2] budget_ceilings[48]
const BUDGET_CEILINGS_OFFSET: usize = 8 + 32 + 12 + 12 + 12 + 2; // = 78

// ── Program ───────────────────────────────────────────────────────────────────

#[program]
pub mod cgae_escrow {
    use super::*;

    pub fn initialize(ctx: Context<InitializeEscrow>, registry_program: Pubkey) -> Result<()> {
        let s = &mut ctx.accounts.escrow_state;
        s.admin = ctx.accounts.admin.key();
        s.registry_program = registry_program;
        s.total_rewards_paid = 0;
        s.total_penalties_collected = 0;
        s.contract_count = 0;
        s.bump = ctx.bumps.escrow_state;
        Ok(())
    }

    /// Create a contract. Reward is transferred from issuer to PDA in the same tx.
    pub fn create_contract(
        ctx: Context<CreateContract>,
        nonce: u64,
        reward: u64,
        constraints_hash: [u8; 32],
        verifier_spec_cid: String,
        domain: String,
        min_tier: u8,
        penalty: u64,
        deadline: i64,
    ) -> Result<()> {
        require!(reward > 0, EscrowError::ZeroReward);
        require!(verifier_spec_cid.len() <= 128, EscrowError::VerifierCidTooLong);
        require!(domain.len() <= 32, EscrowError::DomainTooLong);
        require!(min_tier >= 1 && min_tier <= 5, EscrowError::InvalidTier);
        require!(deadline > Clock::get()?.unix_timestamp, EscrowError::DeadlinePassed);

        // Transfer reward from issuer into contract PDA
        system_program::transfer(
            CpiContext::new(
                system_program::ID,
                system_program::Transfer {
                    from: ctx.accounts.issuer.to_account_info(),
                    to: ctx.accounts.economic_contract.to_account_info(),
                },
            ),
            reward,
        )?;

        // Build a deterministic contract_id from issuer pubkey + nonce
        let mut contract_id = [0u8; 32];
        let issuer_bytes = ctx.accounts.issuer.key().to_bytes();
        let nonce_bytes = nonce.to_le_bytes();
        contract_id[..32].copy_from_slice(&issuer_bytes);
        for i in 0..8 { contract_id[i] ^= nonce_bytes[i]; }

        let c = &mut ctx.accounts.economic_contract;
        c.contract_id = contract_id;
        c.issuer = ctx.accounts.issuer.key();
        c.assigned_agent = Pubkey::default();
        c.constraints_hash = constraints_hash;
        c.verifier_spec_cid = verifier_spec_cid.clone();
        c.domain = domain.clone();
        c.min_tier = min_tier;
        c.reward = reward;
        c.penalty = penalty;
        c.deadline = deadline;
        c.created_at = Clock::get()?.unix_timestamp;
        c.status = ContractStatus::Open;
        c.bump = ctx.bumps.economic_contract;

        ctx.accounts.escrow_state.contract_count += 1;

        emit!(ContractCreated { contract_id, min_tier, domain });
        Ok(())
    }

    /// Agent accepts a contract. Deposits penalty collateral into PDA.
    /// Reads agent tier/active and budget ceiling directly from registry PDAs.
    pub fn accept_contract(ctx: Context<AcceptContract>, active_exposure: u64) -> Result<()> {
        {
            let c = &ctx.accounts.economic_contract;
            require!(c.status == ContractStatus::Open, EscrowError::NotOpen);
            require!(Clock::get()?.unix_timestamp < c.deadline, EscrowError::DeadlinePassed);
        }

        // Read agent tier and active flag from registry AgentRecord account data
        let agent_data = ctx.accounts.agent_record.try_borrow_data()?;
        require!(agent_data.len() > AGENT_ACTIVE_OFFSET, EscrowError::AgentNotActive);
        let agent_tier   = agent_data[AGENT_TIER_OFFSET];
        let agent_active = agent_data[AGENT_ACTIVE_OFFSET] != 0;
        drop(agent_data);

        require!(agent_active, EscrowError::AgentNotActive);

        let (min_tier, penalty, contract_id) = {
            let c = &ctx.accounts.economic_contract;
            (c.min_tier, c.penalty, c.contract_id)
        };

        require!(agent_tier >= min_tier, EscrowError::TierTooLow);

        // Read budget ceiling for agent's tier from registry RegistryConfig account data
        let config_data = ctx.accounts.registry_config.try_borrow_data()?;
        let ceiling_start = BUDGET_CEILINGS_OFFSET + (agent_tier as usize) * 8;
        require!(config_data.len() >= ceiling_start + 8, EscrowError::TierTooLow);
        let ceiling = u64::from_le_bytes(
            config_data[ceiling_start..ceiling_start + 8].try_into().unwrap()
        );
        drop(config_data);

        require!(
            active_exposure.saturating_add(penalty) <= ceiling,
            EscrowError::BudgetCeilingExceeded
        );

        // Transfer penalty collateral from agent to contract PDA
        system_program::transfer(
            CpiContext::new(
                system_program::ID,
                system_program::Transfer {
                    from: ctx.accounts.agent.to_account_info(),
                    to: ctx.accounts.economic_contract.to_account_info(),
                },
            ),
            penalty,
        )?;

        let c = &mut ctx.accounts.economic_contract;
        c.assigned_agent = ctx.accounts.agent.key();
        c.status = ContractStatus::Assigned;

        emit!(ContractAssigned { contract_id, agent: c.assigned_agent });
        Ok(())
    }

    /// Complete a contract. Releases reward + collateral to agent.
    pub fn complete_contract(ctx: Context<SettleContract>) -> Result<()> {
        let c = &ctx.accounts.economic_contract;
        require!(c.status == ContractStatus::Assigned, EscrowError::NotAssigned);
        require!(ctx.accounts.recipient.key() == c.assigned_agent, EscrowError::RecipientMismatch);
        require!(ctx.accounts.issuer.key() == c.issuer, EscrowError::IssuerMismatch);

        let payout = c.reward.saturating_add(c.penalty);
        let reward = c.reward;
        let contract_id = c.contract_id;
        let agent = c.assigned_agent;

        ctx.accounts.economic_contract.status = ContractStatus::Completed;

        **ctx.accounts.economic_contract.to_account_info().try_borrow_mut_lamports()? -= payout;
        **ctx.accounts.recipient.try_borrow_mut_lamports()? += payout;

        ctx.accounts.escrow_state.total_rewards_paid =
            ctx.accounts.escrow_state.total_rewards_paid.saturating_add(reward);

        emit!(ContractCompleted { contract_id, agent, reward });
        Ok(())
    }

    /// Fail a contract. Penalty forfeited; reward returned to issuer.
    pub fn fail_contract(ctx: Context<SettleContract>) -> Result<()> {
        let c = &ctx.accounts.economic_contract;
        require!(c.status == ContractStatus::Assigned, EscrowError::NotAssigned);
        require!(ctx.accounts.issuer.key() == c.issuer, EscrowError::IssuerMismatch);

        let reward = c.reward;
        let penalty = c.penalty;
        let contract_id = c.contract_id;
        let agent = c.assigned_agent;

        ctx.accounts.economic_contract.status = ContractStatus::Failed;

        **ctx.accounts.economic_contract.to_account_info().try_borrow_mut_lamports()? -= reward;
        **ctx.accounts.issuer.try_borrow_mut_lamports()? += reward;

        ctx.accounts.escrow_state.total_penalties_collected =
            ctx.accounts.escrow_state.total_penalties_collected.saturating_add(penalty);

        emit!(ContractFailed { contract_id, agent, penalty });
        Ok(())
    }

    /// Expire an open contract past its deadline. Returns reward to issuer.
    pub fn expire_contract(ctx: Context<ExpireContract>) -> Result<()> {
        let c = &ctx.accounts.economic_contract;
        require!(c.status == ContractStatus::Open, EscrowError::NotOpen);
        require!(Clock::get()?.unix_timestamp >= c.deadline, EscrowError::NotExpired);
        require!(ctx.accounts.issuer.key() == c.issuer, EscrowError::IssuerMismatch);

        let reward = c.reward;
        let contract_id = c.contract_id;

        ctx.accounts.economic_contract.status = ContractStatus::Expired;

        **ctx.accounts.economic_contract.to_account_info().try_borrow_mut_lamports()? -= reward;
        **ctx.accounts.issuer.try_borrow_mut_lamports()? += reward;

        emit!(ContractExpired { contract_id });
        Ok(())
    }
}

// ── Accounts ──────────────────────────────────────────────────────────────────

#[derive(Accounts)]
pub struct InitializeEscrow<'info> {
    #[account(init, payer = admin, space = EscrowState::LEN, seeds = [b"escrow_state"], bump)]
    pub escrow_state: Account<'info, EscrowState>,
    #[account(mut)]
    pub admin: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(nonce: u64)]
pub struct CreateContract<'info> {
    #[account(mut, seeds = [b"escrow_state"], bump = escrow_state.bump)]
    pub escrow_state: Account<'info, EscrowState>,
    #[account(
        init, payer = issuer, space = EconomicContract::LEN,
        seeds = [b"contract", issuer.key().as_ref(), &nonce.to_le_bytes()], bump
    )]
    pub economic_contract: Account<'info, EconomicContract>,
    #[account(mut)]
    pub issuer: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct AcceptContract<'info> {
    #[account(seeds = [b"escrow_state"], bump = escrow_state.bump)]
    pub escrow_state: Account<'info, EscrowState>,
    #[account(mut)]
    pub economic_contract: Account<'info, EconomicContract>,
    /// CHECK: AgentRecord PDA from cgae_registry — we read raw bytes
    pub agent_record: UncheckedAccount<'info>,
    /// CHECK: RegistryConfig PDA from cgae_registry — we read raw bytes
    pub registry_config: UncheckedAccount<'info>,
    #[account(mut)]
    pub agent: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct SettleContract<'info> {
    #[account(mut, seeds = [b"escrow_state"], bump = escrow_state.bump, has_one = admin)]
    pub escrow_state: Account<'info, EscrowState>,
    #[account(mut)]
    pub economic_contract: Account<'info, EconomicContract>,
    /// CHECK: verified in handler (must match assigned_agent or issuer)
    #[account(mut)]
    pub recipient: UncheckedAccount<'info>,
    /// CHECK: verified in handler (must match issuer)
    #[account(mut)]
    pub issuer: UncheckedAccount<'info>,
    pub admin: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct ExpireContract<'info> {
    #[account(mut)]
    pub economic_contract: Account<'info, EconomicContract>,
    /// CHECK: verified in handler (must match issuer)
    #[account(mut)]
    pub issuer: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}

// ── Events ────────────────────────────────────────────────────────────────────

#[event] pub struct ContractCreated  { pub contract_id: [u8; 32], pub min_tier: u8, pub domain: String }
#[event] pub struct ContractAssigned { pub contract_id: [u8; 32], pub agent: Pubkey }
#[event] pub struct ContractCompleted{ pub contract_id: [u8; 32], pub agent: Pubkey, pub reward: u64 }
#[event] pub struct ContractFailed   { pub contract_id: [u8; 32], pub agent: Pubkey, pub penalty: u64 }
#[event] pub struct ContractExpired  { pub contract_id: [u8; 32] }
