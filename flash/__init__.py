"""
pyflashdb — A unified database interface for MySQL, PostgreSQL, and MongoDB.

Usage:
    from flash import FlashDB
    flash = FlashDB("mysql", config)
"""

from .core import FlashDB
from .exceptions import (
    FlashError,
    FlashConnectionError,   # renamed — does NOT shadow Python's built-in ConnectionError
    QueryError,
    TransactionError,
    SchemaError,
    UnsupportedDatabaseError,
)

__version__ = "1.0.4"
__author__  = "Aman Singh"
__credits__ = "Inspired by Komal Verma"
__license__ = "MIT"

__all__ = [
    "FlashDB",
    # Exceptions — import these, not Python's built-ins
    "FlashError",
    "FlashConnectionError",
    "QueryError",
    "TransactionError",
    "SchemaError",
    "UnsupportedDatabaseError",
]