"""
pyflashdb — PostgreSQL adapter.
Requires: pip install psycopg2-binary
"""

from typing import Any, List, Optional
from ..filters import filters_to_sql, build_update_sql, python_type_to_sql
from ..exceptions import FlashConnectionError, QueryError, TransactionError


class PostgreSQLAdapter:
    """
    PostgreSQL backend — uses psycopg2.
    Instantiated automatically by FlashDB when db_type="postgres".
    """

    def __init__(self, config: dict):
        self.config = config
        self.conn   = None
        self.cursor = None
        self._in_transaction = False
        self._connect()

    # ── Internal helpers ───────────────────────────────────────────────────

    def _connect(self):
        try:
            import psycopg2
            import psycopg2.extras
            self.conn = psycopg2.connect(
                host    = self.config.get("host", "localhost"),
                port    = self.config.get("port", 5432),
                user    = self.config.get("user", "postgres"),
                password= self.config.get("password", ""),
                dbname  = self.config.get("database"),
            )
            self.conn.autocommit = True
            self.cursor = self.conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        except ImportError:
            raise FlashConnectionError(
                "psycopg2 is not installed. Run: pip install psycopg2-binary"
            )
        except Exception as e:
            raise FlashConnectionError(f"PostgreSQL connection failed: {e}")

    def _execute(self, sql: str, params: list = None) -> Any:
        try:
            self.cursor.execute(sql, params if params else None)
            return self.cursor
        except Exception as e:
            if not self._in_transaction:
                self.conn.rollback()
            raise QueryError(
                f"PostgreSQL query failed: {e}\nSQL: {sql}\nParams: {params}"
            )

    def _q(self, name: str) -> str:
        """Double-quote an identifier."""
        return f'"{name}"'

    def _commit(self):
        if not self._in_transaction:
            pass  # autocommit=True handles it

    # ── CRUD ───────────────────────────────────────────────────────────────

    def all(self, table: str) -> List[dict]:
        self._execute(f"SELECT * FROM {self._q(table)}")
        return [dict(r) for r in self.cursor.fetchall()]

    def select(
        self,
        table:    str,
        fields:   List[str] = None,
        filters:  dict      = None,
        limit:    int       = None,
        offset:   int       = None,
        order_by: str       = None,
    ) -> List[dict]:
        cols   = ", ".join(self._q(f) for f in fields) if fields else "*"
        sql    = f"SELECT {cols} FROM {self._q(table)}"
        params: list = []

        if filters:
            clause, params = filters_to_sql(filters)
            sql += f" WHERE {clause}"
        if order_by:
            sql += f" ORDER BY {self._q(order_by)}"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
            if offset is not None:
                sql += f" OFFSET {int(offset)}"

        self._execute(sql, params)
        return [dict(r) for r in self.cursor.fetchall()]

    # ── BUG FIX #2 ──────────────────────────────────────────────────────
    # Old code used RETURNING * and returned the whole row as a dict,
    # which is inconsistent with MySQL (returns int).
    # Fixed: use RETURNING id (or the configured primary_key) and return
    # only that integer value.
    # ────────────────────────────────────────────────────────────────────
    def add(self, table: str, data: dict, primary_key: str = "id") -> Any:
        fields       = ", ".join(self._q(k) for k in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql          = (
            f"INSERT INTO {self._q(table)} ({fields}) "
            f"VALUES ({placeholders}) RETURNING {self._q(primary_key)}"
        )
        self._execute(sql, list(data.values()))
        row = self.cursor.fetchone()
        return row[primary_key] if row else None   # returns int, not dict

    def bulk_insert(self, table: str, records: List[dict]) -> int:
        if not records:
            return 0
        fields       = ", ".join(self._q(k) for k in records[0].keys())
        placeholders = ", ".join(["%s"] * len(records[0]))
        sql          = f"INSERT INTO {self._q(table)} ({fields}) VALUES ({placeholders})"
        rows         = [list(r.values()) for r in records]
        try:
            self.cursor.executemany(sql, rows)
            return self.cursor.rowcount
        except Exception as e:
            raise QueryError(f"PostgreSQL bulk insert failed: {e}")

    def update(self, table: str, filters: dict, data: dict) -> int:
        set_clause,   set_params   = build_update_sql(data)
        where_clause, where_params = filters_to_sql(filters)
        sql = f"UPDATE {self._q(table)} SET {set_clause}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        self._execute(sql, set_params + where_params)
        return self.cursor.rowcount

    def delete(self, table: str, filters: dict = None) -> int:
        sql    = f"DELETE FROM {self._q(table)}"
        params: list = []
        if filters:
            clause, params = filters_to_sql(filters)
            sql += f" WHERE {clause}"
        self._execute(sql, params)
        return self.cursor.rowcount

    # ── Schema ─────────────────────────────────────────────────────────────

    def create_table(self, table: str, schema: dict, primary_key: str = "id") -> bool:
        col_defs = []
        has_pk   = False
        for col, typ in schema.items():
            sql_type = python_type_to_sql(typ, "postgres")
            if col == primary_key:
                col_defs.append(f"{self._q(col)} SERIAL PRIMARY KEY")
                has_pk = True
            else:
                col_defs.append(f"{self._q(col)} {sql_type}")
        if not has_pk:
            col_defs.insert(0, f"{self._q(primary_key)} SERIAL PRIMARY KEY")
        self._execute(
            f"CREATE TABLE IF NOT EXISTS {self._q(table)} ({', '.join(col_defs)})"
        )
        return True

    def drop_table(self, table: str) -> bool:
        self._execute(f"DROP TABLE IF EXISTS {self._q(table)}")
        return True

    def truncate(self, table: str) -> bool:
        self._execute(
            f"TRUNCATE TABLE {self._q(table)} RESTART IDENTITY CASCADE"
        )
        return True

    def show_tables(self) -> List[str]:
        self._execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
        return [row["table_name"] for row in self.cursor.fetchall()]

    def describe(self, table: str) -> List[dict]:
        self._execute(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_name = %s "
            "ORDER BY ordinal_position",
            [table],
        )
        return [dict(r) for r in self.cursor.fetchall()]

    # ── Transactions ───────────────────────────────────────────────────────

    def begin(self):
        self.conn.autocommit = False
        self._in_transaction = True

    def commit(self):
        try:
            self.conn.commit()
        except Exception as e:
            raise TransactionError(f"Commit failed: {e}")
        finally:
            self.conn.autocommit = True
            self._in_transaction = False

    def rollback(self):
        try:
            self.conn.rollback()
        except Exception as e:
            raise TransactionError(f"Rollback failed: {e}")
        finally:
            self.conn.autocommit = True
            self._in_transaction = False

    # ── Raw query ──────────────────────────────────────────────────────────

    def raw(self, sql: str, params: list = None) -> Any:
        """
        Execute a raw SQL string.
        Returns list[dict] for SELECT statements, int (rowcount) for others.
        """
        self._execute(sql, params)
        try:
            result = [dict(r) for r in self.cursor.fetchall()]
            return result if result else self.cursor.rowcount
        except Exception:
            return self.cursor.rowcount

    # ── Count ──────────────────────────────────────────────────────────────

    def count(self, table: str, filters: dict = None) -> int:
        sql    = f"SELECT COUNT(*) AS cnt FROM {self._q(table)}"
        params: list = []
        if filters:
            clause, params = filters_to_sql(filters)
            sql += f" WHERE {clause}"
        self._execute(sql, params)
        row = self.cursor.fetchone()
        return int(row["cnt"]) if row else 0

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def close(self):
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
        except Exception:
            pass

    def ping(self) -> bool:
        try:
            self._execute("SELECT 1")
            return True
        except Exception:
            return False