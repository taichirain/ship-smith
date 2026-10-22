import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "ShipSmith API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    public_core_url: str = ""
    install_script_url: str = "https://shipsmith.example.com/install.sh"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/shipsmith"

    jwt_secret_key: str = "change-me-in-production-please"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    git_credentials_secret_key: str = ""

    admin_username: str = "admin"
    admin_password: str = "admin123"

    heartbeat_retention_days: int = 7
    deployment_logs_retention_days: int = 30
    webhook_payload_retention_days: int = 14
    notification_deliveries_retention_days: int = 30
    flag_audits_retention_days: int = 90
    project_audits_retention_days: int = 90

    agent_offline_threshold_seconds: int = 600
    agent_monitor_interval_seconds: int = 60
    health_monitor_enabled: bool = True

    llm_enabled: bool = False
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_api_base: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.3
    llm_timeout: int = 30


def _load_env_from_file() -> None:
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


@lru_cache
def get_settings() -> Settings:
    _load_env_from_file()

    return Settings(
        app_name=os.environ.get("APP_NAME", "ShipSmith API"),
        app_version=os.environ.get("APP_VERSION", "0.1.0"),
        api_prefix=os.environ.get("API_PREFIX", "/api/v1"),
        public_core_url=os.environ.get("PUBLIC_CORE_URL", ""),
        install_script_url=os.environ.get("INSTALL_SCRIPT_URL", "https://shipsmith.example.com/install.sh"),
        database_url=os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/shipsmith"),
        jwt_secret_key=os.environ.get("JWT_SECRET_KEY", "change-me-in-production-please"),
        jwt_algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
        jwt_expire_minutes=int(os.environ.get("JWT_EXPIRE_MINUTES", "1440")),
        git_credentials_secret_key=os.environ.get("GIT_CREDENTIALS_SECRET_KEY", ""),
        admin_username=os.environ.get("ADMIN_USERNAME", "admin"),
        admin_password=os.environ.get("ADMIN_PASSWORD", "admin123"),
        heartbeat_retention_days=int(os.environ.get("HEARTBEAT_RETENTION_DAYS", "7")),
        deployment_logs_retention_days=int(os.environ.get("DEPLOYMENT_LOGS_RETENTION_DAYS", "30")),
        webhook_payload_retention_days=int(os.environ.get("WEBHOOK_PAYLOAD_RETENTION_DAYS", "14")),
        notification_deliveries_retention_days=int(os.environ.get("NOTIFICATION_DELIVERIES_RETENTION_DAYS", "30")),
        flag_audits_retention_days=int(os.environ.get("FLAG_AUDITS_RETENTION_DAYS", "90")),
        project_audits_retention_days=int(os.environ.get("PROJECT_AUDITS_RETENTION_DAYS", "90")),
        agent_offline_threshold_seconds=int(os.environ.get("AGENT_OFFLINE_THRESHOLD_SECONDS", "600")),
        agent_monitor_interval_seconds=int(os.environ.get("AGENT_MONITOR_INTERVAL_SECONDS", "60")),
        health_monitor_enabled=os.environ.get("HEALTH_MONITOR_ENABLED", "true").lower() == "true",
        llm_enabled=os.environ.get("LLM_ENABLED", "false").lower() == "true",
        llm_provider=os.environ.get("LLM_PROVIDER", "openai"),
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
        llm_api_base=os.environ.get("LLM_API_BASE", ""),
        llm_model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        llm_temperature=float(os.environ.get("LLM_TEMPERATURE", "0.3")),
        llm_timeout=int(os.environ.get("LLM_TIMEOUT", "30")),
    )
