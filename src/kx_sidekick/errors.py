class KxSidekickError(Exception):
    """Base exception for kx_sidekick."""


class ConfigError(KxSidekickError):
    """Raised when configuration is invalid."""


class CollectorError(KxSidekickError):
    """Raised when a collector cannot fetch messages."""


class DatabaseError(KxSidekickError):
    """Raised when database access fails."""


class UnsupportedModeError(KxSidekickError):
    """Raised when a collector mode is declared but not implemented."""


class NotificationError(KxSidekickError):
    """Raised when sending an exit notification fails."""
