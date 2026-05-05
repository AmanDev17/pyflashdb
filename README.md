#  Flash — Unified Database Interface

Flash is a lightweight Python library that gives you one clean API for **MySQL**, **PostgreSQL**, and **MongoDB** — with built-in trigger hooks, no models required.

```python
from flash import FlashDB

flash = FlashDB("mysql", config)
flash.add("users", {"name": "John", "age": 25})
flash.where("users", {"age": {">": 18}})
```

---

## 📦 Installation

```bash
pip install flashdb

# With specific driver:
pip install flashdb[mysql]      # MySQL
pip install flashdb[postgres]   # PostgreSQL
pip install flashdb[mongodb]    # MongoDB
pip install flashdb[all]        # All drivers
```

---

## 🔌 Connection

### MySQL
```python
from flash import FlashDB

flash = FlashDB("mysql", {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "1234",
    "database": "mydb"
})
```

### PostgreSQL
```python
flash = FlashDB("postgres", {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "1234",
    "database": "mydb"
})
```

### MongoDB
```python
flash = FlashDB("mongodb", {
    "host": "localhost",
    "port": 27017,
    "database": "mydb"
    # Or use: "uri": "mongodb+srv://..."
})
```

### Context Manager
```python
with FlashDB("mysql", config) as flash:
    flash.add("users", {"name": "John"})
# Connection auto-closed
```

---

## 🧩 CRUD Operations

### ➕ Insert

```python
# Single record
flash.add("users", {"name": "Alice", "age": 22})

# Bulk insert
flash.bulk_insert("users", [
    {"name": "Alice", "age": 22},
    {"name": "Bob", "age": 30},
])
```

### 📖 Read

```python
# All records
flash.all("users")

# With filters
flash.where("users", {"name": "Alice"})
flash.where("users", {"age": {">": 18}})

# Specific fields
flash.select("users", fields=["name", "age"])

# Combined
flash.select("users",
    fields=["name", "age"],
    filters={"age": {">": 18}},
    order_by="age",
    limit=10
)

# Single record
flash.find_one("users", {"name": "Alice"})

# Count
flash.count("users", {"age": {">": 18}})

# Limit
flash.limit("users", 5)

# Paginate
flash.paginate("users", page=2, size=10)
# Returns: {"data": [...], "page": 2, "size": 10, "total": 42}
```

### ✏️ Update

```python
flash.update("users", {"name": "Alice"}, {"age": 23})
```

### 🗑️ Delete

```python
flash.delete("users", {"name": "Alice"})
```

---

## 🔍 Filter Operators

Flash uses a unified filter syntax that automatically translates to SQL or MongoDB:

| Flash Operator | SQL       | MongoDB  |
|---------------|-----------|----------|
| `>`           | `>`       | `$gt`    |
| `<`           | `<`       | `$lt`    |
| `>=`          | `>=`      | `$gte`   |
| `<=`          | `<=`      | `$lte`   |
| `!=`          | `!=`      | `$ne`    |
| `in`          | `IN`      | `$in`    |
| `not in`      | `NOT IN`  | `$nin`   |
| `like`        | `LIKE`    | `$regex` |

```python
flash.where("users", {"age": {">": 18}})
flash.where("users", {"role": {"in": ["admin", "mod"]}})
flash.where("users", {"name": {"like": "Jo%"}})
flash.where("users", {"score": {">=": 80, "<=": 100}})
```

---

## 🔔 Trigger Hooks

Flash supports before/after hooks for all operations — even on MongoDB where native triggers don't exist.

### Decorator Style

```python
@flash.before_insert("users")
def validate(data):
    if not data.get("name"):
        raise ValueError("Name is required")

@flash.after_insert("users")
def on_created(data, result):
    print(f"New user created with ID: {result}")

@flash.before_update("users")
def log_update(payload):
    print("Updating:", payload["filters"], "->", payload["data"])

@flash.after_delete("users")
def on_deleted(filters, count):
    print(f"Deleted {count} record(s)")
```

### Programmatic Style

```python
def audit_log(data):
    print("Insert:", data)

flash.add_hook("before", "insert", "users", audit_log)
```

### Available Hooks

| Hook                         | When it fires                  |
|-----------------------------|--------------------------------|
| `before_insert(table)`      | Before `add()` or `bulk_insert()`  |
| `after_insert(table)`       | After `add()` or `bulk_insert()`   |
| `before_update(table)`      | Before `update()`              |
| `after_update(table)`       | After `update()`               |
| `before_delete(table)`      | Before `delete()`              |
| `after_delete(table)`       | After `delete()`               |
| `before_select(table)`      | Before `all()`, `select()`, `where()` |
| `after_select(table)`       | After any read operation       |

### Manage Hooks

```python
flash.list_hooks()          # See all registered hooks
flash.clear_hooks()         # Remove all hooks
flash.clear_hooks("users")  # Remove hooks for one table
```

---

## 📄 Schema Operations

```python
# Create table/collection
flash.create_table("users", {
    "id": "int",
    "name": "str",
    "email": "str",
    "age": "int",
    "score": "float"
})

# Drop table
flash.drop_table("users")

# Truncate (keep structure, delete data)
flash.truncate("users")

# List tables
flash.show_tables()

# Describe structure
flash.describe("users")
```

### Supported Type Strings

| Flash Type | MySQL          | PostgreSQL     |
|-----------|----------------|----------------|
| `int`     | INT            | INTEGER        |
| `str`     | VARCHAR(255)   | VARCHAR(255)   |
| `text`    | TEXT           | TEXT           |
| `float`   | FLOAT          | REAL           |
| `bool`    | TINYINT(1)     | BOOLEAN        |
| `date`    | DATE           | DATE           |
| `datetime`| DATETIME       | TIMESTAMP      |
| `json`    | JSON           | JSONB          |

---

## 🔐 Transactions (SQL)

```python
flash.begin()
try:
    flash.add("accounts", {"user": "Alice", "balance": 500})
    flash.update("accounts", {"user": "Bob"}, {"balance": 100})
    flash.commit()
except Exception:
    flash.rollback()
```

---

## 🧰 Raw Queries

```python
# SQL
flash.raw("SELECT * FROM users WHERE age > %s", [18])

# MongoDB (pass raw filter dict)
flash.raw({"age": {"$gt": 18}}, table="users")
```

---

## 🍃 MongoDB-Specific

```python
# Aggregation pipeline
flash.aggregate("orders", [
    {"$match": {"status": "paid"}},
    {"$group": {"_id": "$user_id", "total": {"$sum": "$amount"}}},
    {"$sort": {"total": -1}}
])

# Create index
flash.create_index("users", "email", unique=True)
```

---

## 🔧 Utilities

```python
flash.ping()    # True if connection is alive
flash.close()   # Close connection
```

---

## 📁 Project Structure

```
flash/
├── flash/
│   ├── __init__.py         # Package entry point
│   ├── core.py             # FlashDB main class
│   ├── filters.py          # Filter/query translation
│   ├── triggers.py         # Hook/trigger system
│   ├── exceptions.py       # Custom exceptions
│   └── adapters/
│       ├── __init__.py
│       ├── mysql_adapter.py
│       ├── postgres_adapter.py
│       └── mongo_adapter.py
├── setup.py
└── README.md
```

---

## 📜 License

MIT © Flash Team
