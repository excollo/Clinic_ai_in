"""Application-level exceptions."""


class ConfigurationError(RuntimeError):
    """Raised when required configuration or feature wiring is invalid or incomplete."""


class StorageError(RuntimeError):
    """Raised when audio storage cannot guarantee durability."""
