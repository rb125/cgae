use anchor_lang::prelude::*;
use crate::state::*;

#[derive(Accounts)]
pub struct InitializeEscrow<'info> {
    #[account(
        init,
        payer = admin,
        space = EscrowState::LEN,
        seeds = [b"escrow_state"],
        bump
    )]
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
        init,
        payer = issuer,
        space = EconomicContract::LEN,
        seeds = [b"contract", issuer.key().as_ref(), &nonce.to_le_bytes()],
        bump
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

    /// Agent's registry record — read-only, verified via seeds on registry program
    /// CHECK: We read tier/active from this account; seeds verified by registry program
    pub agent_record: UncheckedAccount<'info>,

    /// Registry config for budget ceiling lookup
    /// CHECK: seeds verified by registry program
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

    /// CHECK: recipient of funds — verified in handler
    #[account(mut)]
    pub recipient: UncheckedAccount<'info>,

    /// CHECK: issuer for refund on failure
    #[account(mut)]
    pub issuer: UncheckedAccount<'info>,

    pub admin: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct ExpireContract<'info> {
    #[account(mut)]
    pub economic_contract: Account<'info, EconomicContract>,

    /// CHECK: issuer receives refund
    #[account(mut)]
    pub issuer: UncheckedAccount<'info>,

    pub system_program: Program<'info, System>,
}
