"""
pyflashdb — MongoDB adapter.
Requires: pip install pymongo
"""

from typing import Any, List, Optional
from ..filters import filters_to_mongo
from ..exceptions import FlashConnectionError, QueryError


class MongoAdapter:
    """
    MongoDB backend — uses pymongo.
    Instantiated automatically by FlashDB when db_type="mongodb".
    """

    def __init__(self, config: dict):
        self.config   = config
        self.client   = None
        self.db       = None
        self._session = None
        self._connect()

    # ── Internal helpers ───────────────────────────────────────────────────

    def _connect(self):
        try:
            from pymongo import MongoClient

            uri  = self.config.get("uri")
            user = self.config.get("user")
            pwd  = self.config.get("password")

            if uri:
                self.client = MongoClient(uri)
            elif user and pwd:
                self.client = MongoClient(
                    host     = self.config.get("host", "localhost"),
                    port     = self.config.get("port", 27017),
                    username = user,
                    password = pwd,
                )
            else:
                self.client = MongoClient(
                    host = self.config.get("host", "localhost"),
                    port = self.config.get("port", 27017),
                )

            self.db = self.client[self.config.get("database", "flash_db")]
            # Verify connection
            self.client.admin.command("ping")

        except ImportError:
            raise FlashConnectionError(
                "pymongo is not installed. Run: pip install pymongo"
            )
        except Exception as e:
            raise FlashConnectionError(f"MongoDB connection failed: {e}")

    def _col(self, table: str):
        """Return the pymongo Collection for the given name."""
        return self.db[table]

    def _clean(self, doc: dict) -> dict:
        """Stringify ObjectId so the result is always JSON-serialisable."""
        if doc and "_id" in doc:
            doc = dict(doc)
            doc["_id"] = str(doc["_id"])
        return doc

    # ── CRUD ───────────────────────────────────────────────────────────────

    def all(self, table: str) -> List[dict]:
        return [self._clean(d) for d in self._col(table).find()]

    def select(
        self,
        table:    str,
        fields:   List[str] = None,
        filters:  dict      = None,
        limit:    int       = None,
        offset:   int       = None,
        order_by: str       = None,
    ) -> List[dict]:
        query      = filters_to_mongo(filters) if filters else {}
        projection = {f: 1 for f in fields} if fields else None

        cursor = self._col(table).find(query, projection)

        if order_by:
            direction = -1 if order_by.startswith("-") else 1
            field     = order_by.lstrip("-")
            cursor    = cursor.sort(field, direction)

        if offset:
            cursor = cursor.skip(int(offset))
        if limit:
            cursor = cursor.limit(int(limit))

        return [self._clean(d) for d in cursor]

    def add(self, table: str, data: dict, primary_key: str = "id") -> str:
        """Insert one document. Returns the string representation of ObjectId."""
        try:
            result = self._col(table).insert_one(data.copy())
            return str(result.inserted_id)
        except Exception as e:
            raise QueryError(f"MongoDB insert failed: {e}")

    def bulk_insert(self, table: str, records: List[dict]) -> int:
        if not records:
            return 0
        try:
            result = self._col(table).insert_many([r.copy() for r in records])
            return len(result.inserted_ids)
        except Exception as e:
            raise QueryError(f"MongoDB bulk insert failed: {e}")

    def update(self, table: str, filters: dict, data: dict) -> int:
        query = filters_to_mongo(filters)
        try:
            result = self._col(table).update_many(query, {"$set": data})
            return result.modified_count
        except Exception as e:
            raise QueryError(f"MongoDB update failed: {e}")

    def delete(self, table: str, filters: dict = None) -> int:
        query = filters_to_mongo(filters) if filters else {}
        try:
            result = self._col(table).delete_many(query)
            return result.deleted_count
        except Exception as e:
            raise QueryError(f"MongoDB delete failed: {e}")

    # ── Schema / Collections ───────────────────────────────────────────────

    def create_table(self, table: str, schema: dict = None, primary_key: str = "id") -> bool:
        """
        MongoDB creates collections implicitly on first insert.
        If a schema dict is provided, a JSON Schema validator is applied.
        """
        if schema:
            props = {
                field: {"bsonType": self._py_to_bson(typ)}
                for field, typ in schema.items()
            }
            validator = {"$jsonSchema": {"bsonType": "object", "properties": props}}
            if table in self.db.list_collection_names():
                self.db.command("collMod", table, validator=validator)
            else:
                self.db.create_collection(table, validator=validator)
        else:
            if table not in self.db.list_collection_names():
                self.db.create_collection(table)
        return True

    def drop_table(self, table: str) -> bool:
        self._col(table).drop()
        return True

    def truncate(self, table: str) -> bool:
        self._col(table).delete_many({})
        return True

    def show_tables(self) -> List[str]:
        return self.db.list_collection_names()

    def describe(self, table: str) -> dict:
        return self.db.command("collStats", table)

    def create_index(self, table: str, field: str, unique: bool = False) -> str:
        from pymongo import ASCENDING
        return self._col(table).create_index([(field, ASCENDING)], unique=unique)

    # ── Aggregation ────────────────────────────────────────────────────────

    def aggregate(self, table: str, pipeline: list) -> List[dict]:
        return [self._clean(d) for d in self._col(table).aggregate(pipeline)]

    # ── Transactions (requires replica set, MongoDB 4.0+) ──────────────────

    def begin(self):
        self._session = self.client.start_session()
        self._session.start_transaction()

    def commit(self):
        if self._session:
            self._session.commit_transaction()
            self._session.end_session()
            self._session = None

    def rollback(self):
        if self._session:
            self._session.abort_transaction()
            self._session.end_session()
            self._session = None

    # ── Raw command ────────────────────────────────────────────────────────

    def raw(self, command, table: str = None) -> Any:
        """
        Execute a raw MongoDB command or filter.
        - Pass a dict + table to run a collection-level find.
        - Pass a string to run a database-level command.
        """
        try:
            if table and isinstance(command, dict):
                return [self._clean(d) for d in self._col(table).find(command)]
            return self.db.command(command)
        except Exception as e:
            raise QueryError(f"MongoDB raw command failed: {e}")

    # ── Count ──────────────────────────────────────────────────────────────

    def count(self, table: str, filters: dict = None) -> int:
        query = filters_to_mongo(filters) if filters else {}
        return self._col(table).count_documents(query)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def close(self):
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass

    def ping(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    # ── Type mapping ───────────────────────────────────────────────────────

    def _py_to_bson(self, type_str: str) -> str:
        mapping = {
            "int":      "int",    "integer":  "int",
            "str":      "string", "string":   "string", "text": "string",
            "float":    "double", "double":   "double",
            "bool":     "bool",   "boolean":  "bool",
            "date":     "date",   "datetime": "date",   "timestamp": "date",
            "list":     "array",
            "dict":     "object", "json":     "object",
        }
        return mapping.get(type_str.lower(), "string")