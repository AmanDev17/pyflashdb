"""
pyflashdb — FlashDB core.

This is the single public class users interact with.
All database-specific logic lives in the adapters.

    from flash import FlashDB

    flash = FlashDB("mysql", config)
    flash.add("users", {"name": "Alice", "age": 25})
    flash.where("users", {"age": {">": 18}})
"""

from typing import Any, List, Optional, Callable
from .exceptions import UnsupportedDatabaseError, FlashError
from .triggers import make_trigger_mixin


class FlashDB(make_trigger_mixin()):
    """
    Unified, trigger-aware database interface.
    Supports MySQL, PostgreSQL, and MongoDB with a single API.

    Parameters
    ----------
    db_type : str
        One of: "mysql", "postgres" / "postgresql", "mongodb" / "mongo"
    config : dict
        Connection settings dict. Keys depend on the database type.

    Examples
    --------
    >>> flash = FlashDB("mysql", {
    ...     "host": "localhost", "user": "root",
    ...     "password": "pass", "database": "mydb"
    ... })
    >>> flash.add("users", {"name": "Alice", "age": 25})
    >>> flash.where("users", {"age": {">": 18}})
    """

    SUPPORTED = ("mysql", "postgres", "postgresql", "mongodb", "mongo")

    def __init__(self, db_type: str, config: dict):
        self.db_type = db_type.lower().strip()
        self.config  = config
        self._init_triggers()
        self._adapter = self._load_adapter()

    # ── Adapter loader ─────────────────────────────────────────────────────

    def _load_adapter(self):
        if self.db_type == "mysql":
            from .adapters.mysql_adapter import MySQLAdapter
            return MySQLAdapter(self.config)
        elif self.db_type in ("postgres", "postgresql"):
            from .adapters.postgres_adapter import PostgreSQLAdapter
            return PostgreSQLAdapter(self.config)
        elif self.db_type in ("mongodb", "mongo"):
            from .adapters.mongo_adapter import MongoAdapter
            return MongoAdapter(self.config)
        else:
            raise UnsupportedDatabaseError(
                f"'{self.db_type}' is not supported. "
                f"Choose from: mysql, postgres, mongodb"
            )

    # ── Read ───────────────────────────────────────────────────────────────

    def all(self, table: str) -> List[dict]:
        """Return every record in the table/collection."""
        self._triggers.fire("before", "select", table, {})
        result = self._adapter.all(table)
        self._triggers.fire("after", "select", table, {}, result)
        return result

    def select(
        self,
        table:    str,
        fields:   List[str] = None,
        filters:  dict      = None,
        limit:    int       = None,
        offset:   int       = None,
        order_by: str       = None,
    ) -> List[dict]:
        """
        Query with optional field projection, filters, sorting, and pagination.

        Parameters
        ----------
        table    : table or collection name
        fields   : list of field names to return (None = all)
        filters  : Flash filter dict, e.g. {"age": {">": 18}}
        limit    : max records to return
        offset   : records to skip (used with limit for manual pagination)
        order_by : field name to sort ascending; prefix "-" for descending
                   (descending only supported natively on MongoDB;
                    SQL adapters sort ascending regardless of prefix)
        """
        payload = {"fields": fields, "filters": filters}
        self._triggers.fire("before", "select", table, payload)
        result = self._adapter.select(
            table, fields=fields, filters=filters,
            limit=limit, offset=offset, order_by=order_by,
        )
        self._triggers.fire("after", "select", table, payload, result)
        return result

    def where(self, table: str, filters: dict, fields: List[str] = None) -> List[dict]:
        """
        Shorthand for a filtered select.

        Examples
        --------
        >>> flash.where("users", {"age": {">": 18}})
        >>> flash.where("users", {"name": "Alice"}, fields=["name", "email"])
        """
        return self.select(table, fields=fields, filters=filters)

    def find_one(self, table: str, filters: dict) -> Optional[dict]:
        """Return the first matching record, or None if nothing matches."""
        results = self.select(table, filters=filters, limit=1)
        return results[0] if results else None

    def count(self, table: str, filters: dict = None) -> int:
        """Count records without fetching them. Efficient on large tables."""
        return self._adapter.count(table, filters)

    def limit(self, table: str, n: int) -> List[dict]:
        """Return the first N records from the table."""
        return self.select(table, limit=n)

    def paginate(self, table: str, page: int = 1, size: int = 10) -> dict:
        """
        Return one page of results plus metadata.

        Returns
        -------
        dict with keys: data, page, size, total
        """
        offset = (page - 1) * size
        data   = self.select(table, limit=size, offset=offset)
        total  = self.count(table)
        return {"data": data, "page": page, "size": size, "total": total}

    # ── Write ──────────────────────────────────────────────────────────────

    def add(self, table: str, data: dict) -> Any:
        """
        Insert a single record.

        Returns
        -------
        int  for MySQL / PostgreSQL (inserted row ID)
        str  for MongoDB (string ObjectId)
        """
        self._triggers.fire("before", "insert", table, data)
        result = self._adapter.add(table, data)
        self._triggers.fire("after", "insert", table, data, result)
        return result

    def bulk_insert(self, table: str, records: List[dict]) -> int:
        """
        Insert multiple records in one operation.

        Returns
        -------
        int  number of records inserted
        """
        self._triggers.fire("before", "insert", table, records)
        result = self._adapter.bulk_insert(table, records)
        self._triggers.fire("after", "insert", table, records, result)
        return result

    def update(self, table: str, filters: dict, data: dict) -> int:
        """
        Update all records matching filters with new field values.

        Returns
        -------
        int  number of records modified
        """
        payload = {"filters": filters, "data": data}
        self._triggers.fire("before", "update", table, payload)
        result = self._adapter.update(table, filters, data)
        self._triggers.fire("after", "update", table, payload, result)
        return result

    def delete(self, table: str, filters: dict = None) -> int:
        """
        Delete records matching filters.
        If filters is None, ALL records in the table are deleted.

        Returns
        -------
        int  number of records deleted
        """
        self._triggers.fire("before", "delete", table, filters or {})
        result = self._adapter.delete(table, filters)
        self._triggers.fire("after", "delete", table, filters or {}, result)
        return result

    # ── Schema ─────────────────────────────────────────────────────────────

    def create_table(self, table: str, schema: dict, primary_key: str = "id") -> bool:
        """
        Create a table (SQL) or collection with optional JSON Schema validation (MongoDB).
        Safe to call repeatedly — uses IF NOT EXISTS for SQL.

        Parameters
        ----------
        table       : name of the table/collection
        schema      : {column_name: type_string}, e.g. {"name": "str", "age": "int"}
        primary_key : column to use as the primary key (SQL only, default "id")
        """
        return self._adapter.create_table(table, schema, primary_key)

    def drop_table(self, table: str) -> bool:
        """Permanently drop a table/collection and all its data."""
        return self._adapter.drop_table(table)

    def truncate(self, table: str) -> bool:
        """Delete all records without dropping the table structure."""
        return self._adapter.truncate(table)

    def show_tables(self) -> List[str]:
        """List all tables/collections in the connected database."""
        return self._adapter.show_tables()

    def describe(self, table: str):
        """Return column/schema information for the table."""
        return self._adapter.describe(table)

    # ── Transactions ───────────────────────────────────────────────────────

    def begin(self):
        """
        Begin a transaction.
        SQL: disables auto-commit until commit() or rollback().
        MongoDB: starts a session (requires replica set, MongoDB 4.0+).
        """
        self._adapter.begin()

    def commit(self):
        """Commit the current transaction and re-enable auto-commit."""
        self._adapter.commit()

    def rollback(self):
        """Roll back the current transaction and re-enable auto-commit."""
        self._adapter.rollback()

    # ── Raw query — BUG FIX #6 ─────────────────────────────────────────────
    # Old code: ignored `table` for SQL and had a params-is-None logic gap.
    # Fixed:    SQL adapters receive (sql, params); MongoDB adapter receives
    #           (command, table=table) so the table argument is actually used.
    # ──────────────────────────────────────────────────────────────────────

    def raw(self, query, params: list = None, table: str = None) -> Any:
        """
        Execute a raw query or command — escape hatch for complex operations.

        SQL databases
        -------------
        flash.raw("SELECT * FROM users WHERE age > %s", [18])
        flash.raw("UPDATE users SET active = 0 WHERE last_login < %s", ["2023-01-01"])

        MongoDB
        -------
        flash.raw({"age": {"$gt": 18}}, table="users")   # collection-level find
        flash.raw("dbStats")                              # db-level command
        """
        if self.db_type in ("mongodb", "mongo"):
            return self._adapter.raw(query, table=table)
        # SQL adapters
        return self._adapter.raw(query, params)

    # ── MongoDB-specific ───────────────────────────────────────────────────

    def aggregate(self, table: str, pipeline: list) -> List[dict]:
        """
        Run a MongoDB aggregation pipeline. MongoDB only.

        Examples
        --------
        >>> flash.aggregate("orders", [
        ...     {"$match":  {"status": "paid"}},
        ...     {"$group":  {"_id": "$user_id", "total": {"$sum": "$amount"}}},
        ...     {"$sort":   {"total": -1}},
        ... ])
        """
        if not hasattr(self._adapter, "aggregate"):
            raise FlashError("aggregate() is only available for MongoDB.")
        return self._adapter.aggregate(table, pipeline)

    def create_index(self, table: str, field: str, unique: bool = False) -> str:
        """Create an index on a MongoDB collection field. MongoDB only."""
        if not hasattr(self._adapter, "create_index"):
            raise FlashError("create_index() is only available for MongoDB.")
        return self._adapter.create_index(table, field, unique)

    # ── Utilities ──────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if the database connection is alive."""
        return self._adapter.ping()

    def close(self):
        """Close the database connection and free resources."""
        self._adapter.close()

    # ── Context-manager protocol ───────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False   # do not suppress exceptions

    def __repr__(self):
        return (
            f"<FlashDB type={self.db_type!r} "
            f"db={self.config.get('database', '?')!r}>"
        )