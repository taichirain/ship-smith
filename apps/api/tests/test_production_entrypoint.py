import os
import subprocess
from pathlib import Path


def test_migrate_subcommand_uses_database_package_dir(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    (db_dir / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")

    pg_isready = bin_dir / "pg_isready"
    pg_isready.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    pg_isready.chmod(0o755)

    alembic = bin_dir / "alembic"
    alembic.write_text("#!/bin/sh\nprintf '%s\\n' \"$PWD|$*\"\n", encoding="utf-8")
    alembic.chmod(0o755)

    entrypoint = Path(__file__).resolve().parents[3] / "docker" / "entrypoint-api.sh"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "SHIPSMITH_DB_DIR": str(db_dir),
            "DB_HOST": "postgres",
            "DB_PORT": "5432",
            "DB_USER": "shipsmith",
            "RUN_MIGRATIONS": "0",
        }
    )

    result = subprocess.run(
        ["bash", str(entrypoint), "migrate"],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )

    assert f"{db_dir}|upgrade head" in result.stdout
