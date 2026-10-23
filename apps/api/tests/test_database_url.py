from shipsmith_db.engine import get_database_url


def test_postgres_url_selects_installed_psycopg2_driver(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/shipsmith")

    assert get_database_url() == "postgresql+psycopg2://user:pass@db:5432/shipsmith"


def test_generated_postgres_url_selects_psycopg2_driver(monkeypatch):
    for name in ("DATABASE_URL", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "pass")
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "shipsmith")

    assert get_database_url() == "postgresql+psycopg2://user:pass@db:5432/shipsmith"
