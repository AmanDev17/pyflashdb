<div align="center">

<br/>

# ⚡ pyflashdb

**Stop writing database code three times.**

[![PyPI](https://img.shields.io/badge/pypi-v1.0.4-E94560?style=flat-square\&logo=pypi\&logoColor=white)](https://pypi.org/project/pyflashdb/)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?style=flat-square\&logo=python\&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-10B981?style=flat-square)](LICENSE)
[![MySQL](https://img.shields.io/badge/MySQL-supported-00758F?style=flat-square\&logo=mysql\&logoColor=white)](https://www.mysql.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-supported-336791?style=flat-square\&logo=postgresql\&logoColor=white)](https://www.postgresql.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-supported-3D8B37?style=flat-square\&logo=mongodb\&logoColor=white)](https://www.mongodb.com/)

<br/>

</div>

---

## What is pyflashdb?

pyflashdb is a Python library that lets you talk to **MySQL**, **PostgreSQL**, and **MongoDB** using the exact same code.

You write one line. It works on all three databases. No SQL knowledge required. No driver switching. No boilerplate.

```python
from flash import FlashDB

flash = FlashDB("mysql", config)   # change to "postgres" or "mongodb" — nothing else changes

flash.add("users", {"name": "Alice", "age": 25})      # insert
flash.where("users", {"age": {">": 18}})              # filter
flash.update("users", {"name": "Alice"}, {"age": 26}) # update
flash.delete("users", {"name": "Alice"})              # delete
```

That's it. Same four lines work on MySQL, PostgreSQL, and MongoDB.

---

## The Problem It Solves

Most projects start with one database and grow to need another. Or your team uses MySQL locally but PostgreSQL in production. Or you want MongoDB for one feature and SQL for another.

Every time you switch databases, you rewrite your query code — because each database has a completely different API.

**Without pyflashdb — three different APIs to learn and maintain:**

```python
# MySQL
cursor.execute("INSERT INTO users (name, age) VALUES (%s, %s)", ("Alice", 25))
conn.commit()

# PostgreSQL — different driver, slightly different syntax
cursor.execute('INSERT INTO "users" (name, age) VALUES (%s, %s) RETURNING id', ("Alice", 25))

# MongoDB — completely different world
db["users"].insert_one({"name": "Alice", "age": 25})
```

**With pyflashdb — one line, any database:**

```python
flash.add("users", {"name": "Alice", "age": 25})
```

Switch your database by changing one word. Your application code stays exactly the same.

---

## Install

```bash
# Pick the database you use
pip install pyflashdb[mysql]      # MySQL
pip install pyflashdb[postgres]   # PostgreSQL
pip install pyflashdb[mongodb]    # MongoDB
pip install pyflashdb[all]        # All three
```

---

## Quick Example — A Complete User System in 20 Lines

```python
from flash import FlashDB

# Connect — swap "mysql" for "postgres" or "mongodb" to change databases
flash = FlashDB("mysql", {
    "host":     "localhost",
    "user":     "root",
    "password": "your_password",
    "database": "myapp"
})

# Create the table
flash.create_table("users", {
    "id":    "int",
    "name":  "str",
    "email": "str",
    "age":   "int",
})

# Insert
flash.add("users", {"name": "Alice", "email": "alice@example.com", "age": 25})
flash.add("users", {"name": "Bob",   "email": "bob@example.com",   "age": 17})

# Read
all_users  = flash.all("users")                          # everyone
adults     = flash.where("users", {"age": {">": 18}})   # filtered
one_user   = flash.find_one("users", {"name": "Alice"}) # single record
page       = flash.paginate("users", page=1, size=10)   # paginated

# Update
flash.update("users", {"name": "Alice"}, {"age": 26})

# Delete
flash.delete("users", {"name": "Bob"})

flash.close()
```

---

## Core Features

### Everything you need for database work

| Feature                     | What it does                                              |
| --------------------------- | --------------------------------------------------------- |
| `add()`                     | Insert one record, returns the new ID                     |
| `bulk_insert()`             | Insert many records in one call                           |
| `all()`                     | Fetch every record from a table                           |
| `where()`                   | Fetch records matching a filter                           |
| `select()`                  | Full query — filter, sort, limit, offset, specific fields |
| `find_one()`                | Get the first match, or None                              |
| `count()`                   | Count records without fetching them                       |
| `paginate()`                | Built-in pagination with total count                      |
| `update()`                  | Update matching records                                   |
| `delete()`                  | Delete matching records                                   |
| `create_table()`            | Create a table or collection                              |
| `drop_table()`              | Drop a table or collection                                |
| `truncate()`                | Clear all rows, keep the structure                        |
| `raw()`                     | Run a raw SQL query or MongoDB command                    |
| `begin / commit / rollback` | Full transaction support                                  |

### Smart filter syntax — write once, works everywhere

```python
flash.where("users", {"age": {">": 18}})
flash.where("users", {"age": {">=": 18, "<=": 65}})
flash.where("users", {"role": {"in": ["admin", "mod"]}})
flash.where("users", {"email": {"like": "%@gmail.com"}})
flash.where("users", {"status": {"!=": "banned"}})
```

---

## Trigger hooks — observe any operation

```python
@flash.before_insert("users")
def validate(data):
    if not data.get("email"):
        raise ValueError("Email is required")

@flash.after_insert("users")
def on_created(data, result):
    print(f"New user created — ID: {result}")

@flash.after_delete("orders")
def on_deleted(filters, count):
    print(f"Deleted {count} order(s)")
```

---

## Transactions — atomic operations

```python
flash.begin()
try:
    flash.update("accounts", {"user_id": 1}, {"balance": 400})
    flash.update("accounts", {"user_id": 2}, {"balance": 600})
    flash.commit()
except Exception as e:
    flash.rollback()
```

---

## How pyflashdb Compares

|                         | pyflashdb | SQLAlchemy | Django ORM | Raw drivers |
| ----------------------- | :-------: | :--------: | :--------: | :---------: |
| Works on MySQL          |     ✅     |      ✅     |      ✅     |      ✅      |
| Works on PostgreSQL     |     ✅     |      ✅     |      ✅     |      ✅      |
| Works on MongoDB        |     ✅     |      ❌     |      ❌     |      ✅      |
| Same API across all DBs |     ✅     |      ❌     |      ❌     |      ❌      |

---

## Links

* **PyPI:** https://pypi.org/project/pyflashdb/
* **Issues:** https://github.com/AmanDev17/pyflashdb/issues

---

## Documentation

📄 [Full Documentation (PDF)](https://github.com/AmanDev17/pyflashdb/blob/main/pyflashdb_v_1.0.4_README.pdf)

<div align="center">

---

##  Dedication

This project carries a small piece of my life with it.

Inspired by someone who means a lot to me —
your presence, support, and the way you see the world quietly shaped this journey.

Not everything in code is just logic.
Some parts come from people who make us better.

— *Aman*

Inspired by Komal 

**pyflashdb v1.0.4** · MIT License · Python 3.8+

*One API. Any database. Zero boilerplate.*

</div>
