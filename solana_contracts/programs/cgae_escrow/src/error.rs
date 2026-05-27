use anchor_lang::prelude::*;

#[error_code]
pub enum EscrowError {
    #[msg("Contract is not open")]
    NotOpen,
    #[msg("Contract is not assigned")]
    NotAssigned,
    #[msg("Contract deadline has passed")]
    DeadlinePassed,
    #[msg("Contract has not expired yet")]
    NotExpired,
    #[msg("Agent is not active")]
    AgentNotActive,
    #[msg("Agent tier is too low for this contract")]
    TierTooLow,
    #[msg("Accepting would exceed agent budget ceiling")]
    BudgetCeilingExceeded,
    #[msg("Insufficient penalty collateral")]
    InsufficientCollateral,
    #[msg("Reward must be greater than zero")]
    ZeroReward,
    #[msg("Invalid min tier (must be 1-5)")]
    InvalidTier,
    #[msg("Verifier spec CID too long (max 128)")]
    VerifierCidTooLong,
    #[msg("Domain too long (max 32)")]
    DomainTooLong,
    #[msg("Recipient mismatch")]
    RecipientMismatch,
    #[msg("Issuer mismatch")]
    IssuerMismatch,
}
