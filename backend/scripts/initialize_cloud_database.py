"""Initialize an empty database, then apply every idempotent migration."""
from pathlib import Path
import os
import psycopg

root = Path(__file__).resolve().parents[1]
url = os.environ["DATABASE_URL"]

with psycopg.connect(url, autocommit=True, connect_timeout=20) as connection:
    initialized = connection.execute("SELECT to_regclass('\"User\"') IS NOT NULL").fetchone()[0]
    if not initialized:
        connection.execute((root / "db" / "schema.sql").read_text(encoding="utf-8"))
    for migration in sorted((root / "db" / "migrations").glob("*.sql")):
        connection.execute(migration.read_text(encoding="utf-8"))
    if os.getenv("LOAD_DEMO_DATA", "true").lower() == "true":
        connection.execute((root / "db" / "seed.sql").read_text(encoding="utf-8"))

print("database_ready")
