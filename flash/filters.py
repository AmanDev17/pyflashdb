"""
pyflashdb — Query filter translation utilities.

Converts Flash's unified filter syntax into:
  • SQL  WHERE clauses  (with %s parameterised placeholders)
  • MongoDB query dicts (with $ operators)

Supported operators
-------------------
  >        greater than
  <        less than
  >=       greater than or equal
  <=       less than or equal
  !=       not equal
  =        equal  (also the plain-value shorthand)
  in       value in list
  not in   value not in list
  like     SQL LIKE / MongoDB $regex  (see bug-fix note below)
"""

from typing import Tuple, List

# Mapping from Flash operator strings to SQL and MongoDB equivalents
OPERATOR_MAP = {
    ">":      {"sql": ">",       "mongo": "$gt"},
    "<":      {"sql": "<",       "mongo": "$lt"},
    ">=":     {"sql": ">=",      "mongo": "$gte"},
    "<=":     {"sql": "<=",      "mongo": "$lte"},
    "!=":     {"sql": "!=",      "mongo": "$ne"},
    "=":      {"sql": "=",       "mongo": "$eq"},
    "in":     {"sql": "IN",      "mongo": "$in"},
    "not in": {"sql": "NOT IN",  "mongo": "$nin"},
    "like":   {"sql": "LIKE",    "mongo": "$regex"},
}


# ── BUG FIX #3 ──────────────────────────────────────────────────────────────
# SQL LIKE wildcards use % and _.  MongoDB $regex uses POSIX/PCRE syntax.
# The old code passed the SQL pattern directly into $regex, so "Jo%" became
# {"$regex": "Jo%"} which matches nothing in MongoDB.
# This helper converts SQL LIKE patterns to regex strings before they reach
# the MongoDB driver.
# ────────────────────────────────────────────────────────────────────────────
def _sql_like_to_regex(pattern: str) -> str:
    """
    Convert a SQL LIKE pattern to an equivalent regex string for MongoDB.

    Conversions
    -----------
    %   →  .*   (match any sequence of characters)
    _   →  .    (match exactly one character)
    All other regex meta-characters are escaped.
    """
    import re as _re

    # Characters that are special in regex but must be treated as literals
    meta = r"\.^$*+?{}[]|()"
    result = []
    for ch in pattern:
        if ch == "%":
            result.append(".*")
        elif ch == "_":
            result.append(".")
        elif ch in meta:
            result.append("\\" + ch)
        else:
            result.append(ch)
    return "".join(result)


def filters_to_sql(filters: dict) -> Tuple[str, List]:
    """
    Convert a Flash filter dict to a SQL WHERE clause + params list.

    Parameters
    ----------
    filters : dict
        e.g.  {"age": {">": 18}, "name": "John"}

    Returns
    -------
    (clause_str, params_list)
        e.g.  ("age > %s AND name = %s", [18, "John"])
        Returns ("", []) when filters is empty or None.
    """
    if not filters:
        return "", []

    clauses: List[str] = []
    params:  List      = []

    for field, value in filters.items():
        if isinstance(value, dict):
            for op, val in value.items():
                sql_op = OPERATOR_MAP.get(op, {}).get("sql", op)
                if op in ("in", "not in"):
                    placeholders = ", ".join(["%s"] * len(val))
                    clauses.append(f"{field} {sql_op} ({placeholders})")
                    params.extend(val)
                else:
                    clauses.append(f"{field} {sql_op} %s")
                    params.append(val)
        else:
            # Plain value → exact equality
            clauses.append(f"{field} = %s")
            params.append(value)

    return " AND ".join(clauses), params


def filters_to_mongo(filters: dict) -> dict:
    """
    Convert a Flash filter dict to a MongoDB query dict.

    Parameters
    ----------
    filters : dict
        e.g.  {"age": {">": 18}, "name": "John"}

    Returns
    -------
    dict
        e.g.  {"age": {"$gt": 18}, "name": "John"}
    """
    if not filters:
        return {}

    query: dict = {}

    for field, value in filters.items():
        if isinstance(value, dict):
            mongo_expr: dict = {}
            for op, val in value.items():
                mongo_op = OPERATOR_MAP.get(op, {}).get("mongo")
                if op == "like":
                    # BUG FIX #3: convert SQL LIKE wildcards to regex
                    val = _sql_like_to_regex(str(val))
                if mongo_op:
                    mongo_expr[mongo_op] = val
                else:
                    mongo_expr[op] = val
            query[field] = mongo_expr
        else:
            # Plain value → exact equality (no operator wrapper needed)
            query[field] = value

    return query


def build_update_sql(data: dict) -> Tuple[str, List]:
    """
    Build a SQL SET clause from an update data dict.

    Parameters
    ----------
    data : dict
        e.g.  {"name": "Alice", "age": 26}

    Returns
    -------
    (set_clause_str, params_list)
        e.g.  ("name = %s, age = %s", ["Alice", 26])
    """
    if not data:
        return "", []

    clauses = [f"{field} = %s" for field in data.keys()]
    params  = list(data.values())
    return ", ".join(clauses), params


def python_type_to_sql(type_str: str, db_type: str = "mysql") -> str:
    """
    Convert a Flash type string (e.g. "int", "str") to a DB-native SQL type.

    Parameters
    ----------
    type_str : str   Flash type name
    db_type  : str   "mysql" or "postgres"
    """
    type_map = {
        "mysql": {
            "int":       "INT",
            "integer":   "INT",
            "str":       "VARCHAR(255)",
            "string":    "VARCHAR(255)",
            "text":      "TEXT",
            "float":     "FLOAT",
            "double":    "DOUBLE",
            "bool":      "TINYINT(1)",
            "boolean":   "TINYINT(1)",
            "date":      "DATE",
            "datetime":  "DATETIME",
            "timestamp": "TIMESTAMP",
            "json":      "JSON",
            "blob":      "BLOB",
        },
        "postgres": {
            "int":       "INTEGER",
            "integer":   "INTEGER",
            "str":       "VARCHAR(255)",
            "string":    "VARCHAR(255)",
            "text":      "TEXT",
            "float":     "REAL",
            "double":    "DOUBLE PRECISION",
            "bool":      "BOOLEAN",
            "boolean":   "BOOLEAN",
            "date":      "DATE",
            "datetime":  "TIMESTAMP",
            "timestamp": "TIMESTAMP",
            "json":      "JSONB",
            "blob":      "BYTEA",
        },
    }

    db_types = type_map.get(db_type, type_map["mysql"])
    return db_types.get(type_str.lower(), type_str.upper())