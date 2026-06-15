# Changelog

## v1.0.4 — Bug Fix Release

### Fixed

- **`FlashConnectionError` rename** (`flash/__init__.py`, `flash/exceptions.py`)
  `ConnectionError` renamed to `FlashConnectionError` throughout the public API.
  The old name silently shadowed Python's built-in `ConnectionError`, breaking
  any code that caught real OS-level networking errors after importing from Flash.
  A private backwards-compatibility alias remains in `flash.exceptions` only.

- **PostgreSQL `add()` return type** (`flash/adapters/postgres_adapter.py`)
  `add()` now returns an `int` primary key (consistent with the MySQL adapter)
  instead of the entire inserted row as a dict. Changed `RETURNING *` to
  `RETURNING id` (or the configured `primary_key`).

- **`like` filter on MongoDB** (`flash/filters.py`)
  SQL LIKE wildcards (`%` → any chars, `_` → one char) are now correctly
  converted to regex equivalents (`.*` and `.`) and regex meta-characters in
  the pattern are escaped before the value is sent to MongoDB's `$regex`.
  Previously `%` was passed verbatim and matched nothing.

- **`__version__` corrected** (`flash/__init__.py`)
  Updated from `"1.0.0"` to `"1.0.4"` to match the PyPI release.

- **All exceptions exported** (`flash/__init__.py`)
  `TransactionError`, `SchemaError`, and `UnsupportedDatabaseError` are now
  exported directly from `flash` in addition to `flash.exceptions`.

- **`raw()` routing fixed** (`flash/core.py`)
  MongoDB's `table` keyword argument is now correctly forwarded to the adapter.
  SQL adapters receive `(sql, params)`; the MongoDB adapter receives
  `(command, table=table)`. Previously `table` was silently ignored for all
  database types.

## v1.0.3

- Initial public PyPI release.