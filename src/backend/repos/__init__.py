"""Per-resource repository functions for the DBSQL data backend (T-206).

The SQLite path lives inline in the routers (existing SQLAlchemy ORM calls).
The DBSQL path lives here — one module per resource, each exporting a small
set of functions that take the caller's strategist_email + OBO token plus
the operation's payload, and return plain dicts suitable for pydantic
parsing on the way out.

Tenancy (F-TM-1): every read filters by ``strategist_email``; every write
stamps it. The router never composes a SQL string itself — everything is
parameterised and routed through ``src/backend/dbsql.py``.
"""
