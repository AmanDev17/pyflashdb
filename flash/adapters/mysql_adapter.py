"""
pyflashdb — MySQL adapter.
Requires: pip install mysql-connector-python
"""

from typing import Any, List, Optional
from ..filters import filters_to_sql, build_update_sql, python_type_to_sql
from ..exceptions import FlashConnectionError, QueryError, TransactionError


class MySQLAdapter:
    """
    MySQL backend — uses mysql-connector-python.
    Instantiated automatically by FlashDB when db_type="mysql".
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
            import mysql.connector
            self.conn = mysql.connector.connect(
                host      = self.config.get("host", "localhost"),
                port      = self.config.get("port", 3306),
                user      = self.config.get("user", "root"),
                password  = self.config.get("password", ""),
                database  = self.config.get("database"),
                autocommit= True,
            )
            self.cursor = self.conn.cursor(dictionary=True)
        except ImportError:
            raise FlashConnectionError(
                "mysql-connector-python is not installed. "
                "Run: pip install mysql-connector-python"
            )
        except Exception as e:
            raise FlashConnectionError(f"MySQL connection failed: {e}")

    def _execute(self, sql: str, params: list = None) -> Any:
        try:
            self.cursor.execute(sql, params or [])
            return self.cursor
        except Exception as e:
            raise QueryError(
                f"MySQL query failed: {e}\nSQL: {sql}\nParams: {params}"
            )

    def _commit(self):
        """Commit only when not inside an explicit transaction."""
        if not self._in_transaction:
            self.conn.commit()

    # ── CRUD ───────────────────────────────────────────────────────────────

    def all(self, table: str) -> List[dict]:
        self._execute(f"SELECT * FROM `{table}`")
        return self.cursor.fetchall()

    def select(
        self,
        table:    str,
        fields:   List[str] = None,
        filters:  dict      = None,
        limit:    int       = None,
        offset:   int       = None,
        order_by: str       = None,
    ) -> List[dict]:
        cols = ", ".join(f"`{f}`" for f in fields) if fields else "*"
        sql  = f"SELECT {cols} FROM `{table}`"
        params: list = []

        if filters:
            clause, params = filters_to_sql(filters)
            sql += f" WHERE {clause}"
        if order_by:
            sql += f" ORDER BY `{order_by}`"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
            if offset is not None:
                sql += f" OFFSET {int(offset)}"

        self._execute(sql, params)
        return self.cursor.fetchall()

    def add(self, table: str, data: dict) -> int:
        fields       = ", ".join(f"`{k}`" for k in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql          = f"INSERT INTO `{table}` ({fields}) VALUES ({placeholders})"
        self._execute(sql, list(data.values()))
        self._commit()
        return self.cursor.lastrowid   # always int for MySQL

    def bulk_insert(self, table: str, records: List[dict]) -> int:
        if not records:
            return 0
        fields       = ", ".join(f"`{k}`" for k in records[0].keys())
        placeholders = ", ".join(["%s"] * len(records[0]))
        sql          = f"INSERT INTO `{table}` ({fields}) VALUES ({placeholders})"
        rows         = [list(r.values()) for r in records]
        try:
            self.cursor.executemany(sql, rows)
            self._commit()
            return self.cursor.rowcount
        except Exception as e:
            raise QueryError(f"MySQL bulk insert failed: {e}")

    def update(self, table: str, filters: dict, data: dict) -> int:
        set_clause,   set_params   = build_update_sql(data)
        where_clause, where_params = filters_to_sql(filters)
        sql = f"UPDATE `{table}` SET {set_clause}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        self._execute(sql, set_params + where_params)
        self._commit()
        return self.cursor.rowcount

    def delete(self, table: str, filters: dict = None) -> int:
        sql    = f"DELETE FROM `{table}`"
        params: list = []
        if filters:
            clause, params = filters_to_sql(filters)
            sql += f" WHERE {clause}"
        self._execute(sql, params)
        self._commit()
        return self.cursor.rowcount

    # ── Schema ─────────────────────────────────────────────────────────────

    def create_table(self, table: str, schema: dict, primary_key: str = "id") -> bool:
        col_defs = []
        has_pk   = False
        for col, typ in schema.items():
            sql_type = python_type_to_sql(typ, "mysql")
            if col == primary_key:
                col_defs.append(f"`{col}` {sql_type} AUTO_INCREMENT PRIMARY KEY")
                has_pk = True
            else:
                col_defs.append(f"`{col}` {sql_type}")
        if not has_pk:
            col_defs.insert(0, f"`{primary_key}` INT AUTO_INCREMENT PRIMARY KEY")
        self._execute(
            f"CREATE TABLE IF NOT EXISTS `{table}` ({', '.join(col_defs)})"
        )
        return True

    def drop_table(self, table: str) -> bool:
        self._execute(f"DROP TABLE IF EXISTS `{table}`")
        return True

    def truncate(self, table: str) -> bool:
        self._execute(f"TRUNCATE TABLE `{table}`")
        return True

    def show_tables(self) -> List[str]:
        self._execute("SHOW TABLES")
        rows = self.cursor.fetchall()
        return [list(r.values())[0] for r in rows]

    def describe(self, table: str) -> List[dict]:
        self._execute(f"DESCRIBE `{table}`")
        return self.cursor.fetchall()

    # ── Transactions ───────────────────────────────────────────────────────

    def begin(self):
        self.conn.autocommit  = False
        self._in_transaction  = True

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
            result = self.cursor.fetchall()
            # fetchall() on a non-SELECT returns [] — return rowcount instead
            return result if result else self.cursor.rowcount
        except Exception:
            return self.cursor.rowcount

    # ── Count ──────────────────────────────────────────────────────────────

    def count(self, table: str, filters: dict = None) -> int:
        sql    = f"SELECT COUNT(*) AS cnt FROM `{table}`"
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
            self.conn.ping(reconnect=True)
            return True
        except Exception:
            return False