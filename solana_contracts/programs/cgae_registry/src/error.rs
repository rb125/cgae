use anchor_lang::prelude::*;

#[error_code]
pub enum RegistryError {
    #[msg("Agent already registered")]
    AlreadyRegistered,
    #[msg("Agent not registered")]
    NotRegistered,
    #[msg("Model name too long (max 64 chars)")]
    ModelNameTooLong,
    #[msg("Audit CID too long (max 128 chars)")]
    AuditCidTooLong,
    #[msg("Audit type too long (max 32 chars)")]
    AuditTypeTooLong,
}
