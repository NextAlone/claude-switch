"""Exception hierarchy for claude-switch."""

class ClaudeSwitchError(Exception):
    """Base exception for all claude-switch errors."""
    pass


class ProviderNotFoundError(ClaudeSwitchError):
    """Provider name or alias not found."""
    pass


class ConfigError(ClaudeSwitchError):
    """Config file missing, invalid TOML, or bad structure."""
    pass


class CredentialError(ClaudeSwitchError):
    """Failed to read/write credentials (Keychain or file)."""
    pass


class AccountNotFoundError(ClaudeSwitchError):
    """Account name/number not found."""
    pass
