class TgDigestError(Exception):
    """Base exception for tg_digest."""


class ConfigError(TgDigestError):
    """Raised when configuration is invalid."""


class CollectorError(TgDigestError):
    """Raised when a collector cannot fetch messages."""


class UnsupportedModeError(TgDigestError):
    """Raised when a collector mode is declared but not implemented."""
