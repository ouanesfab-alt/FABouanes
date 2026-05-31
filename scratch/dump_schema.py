import os
import sys
import subprocess
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import _ensure_postgres_cluster, _stop_postgres_cluster, _reset_database, _find_pg_binary, PG_PORT, PG_DB, PG_USER, PG_PASSWORD
from app.core.schema_bootstrap import bootstrap_schema

def main():
    print("Ensuring temporary PostgreSQL cluster is running...")
    _ensure_postgres_cluster()
    
    print("Resetting database...")
    _reset_database()
    
    print("Bootstrapping schema...")
    os.environ["DATABASE_URL"] = f"postgresql://{PG_USER}:{PG_PASSWORD}@127.0.0.1:{PG_PORT}/{PG_DB}"
    bootstrap_schema()
    
    print("Running migrations...")
    # Run alembic upgrade head
    env = os.environ.copy()
    env["DATABASE_URL"] = f"postgresql://{PG_USER}:{PG_PASSWORD}@127.0.0.1:{PG_PORT}/{PG_DB}"
    # Wait, in run_alembic_upgrade, it checks if alembic_version exists. If not, it stamps with "base"
    # Let's run: alembic stamp base, then alembic upgrade head
    subprocess.run(["alembic", "stamp", "base"], check=True, env=env)
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=env)
    
    print("Migrations complete. Dumping schema...")
    pg_dump = _find_pg_binary("pg_dump.exe")
    dump_file = Path(__file__).parent / "schema_dump.sql"
    
    cmd = [
        pg_dump,
        "-h", "127.0.0.1",
        "-p", str(PG_PORT),
        "-U", PG_USER,
        "-d", PG_DB,
        "--schema-only",
        "-f", str(dump_file)
    ]
    subprocess.run(cmd, check=True)
    print(f"Schema dumped to {dump_file}")
    
    print("Stopping PostgreSQL cluster...")
    _stop_postgres_cluster()

if __name__ == "__main__":
    main()
