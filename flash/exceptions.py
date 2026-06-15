"""
pyflashdb — Custom exception hierarchy.

Import from here (or from flash directly) rather than using Python's
built-in names so you never accidentally shadow ConnectionError etc.

    from flash import FlashConnectionError, QueryError
    from flash.exceptions import FlashConnectionError
"""


class FlashError(Exception):
    """Base exception for all pyflashdb errors."""
    pass


# ── BUG FIX #1 ──────────────────────────────────────────────────────────────
# Old name was ConnectionError, which shadows Python's built-in ConnectionError.
# Renamed to FlashConnectionError.  A compatibility alias is kept so any code
# that already does `from flash.exceptions import ConnectionError` still works,
# but the preferred name is FlashConnectionError.
# ────────────────────────────────────────────────────────────────────────────
class FlashConnectionError(FlashError):
    """Raised when a database connection fails."""
    pass

# Backwards-compatibility alias — do NOT re-export this from __init__.py
ConnectionError = FlashConnectionError   # noqa: A001


class QueryError(FlashError):
    """Raised when a query fails to execute."""
    pass


class UnsupportedDatabaseError(FlashError):
    """Raised when an unsupported database type is passed to FlashDB()."""
    pass


class TransactionError(FlashError):
    """Raised when a transaction commit or rollback fails."""
    pass


class SchemaError(FlashError):
    """Raised when a schema operation (create/drop/truncate) fails."""
    pass