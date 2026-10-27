import pytest

from shipsmith_api.config import Settings, validate_runtime_settings


def test_development_defaults_are_allowed():
    validate_runtime_settings(Settings())


def test_production_defaults_are_rejected():
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_settings(Settings(environment="production"))

    message = str(exc.value)
    assert "JWT_SECRET_KEY" in message
    assert "ADMIN_PASSWORD" in message


def test_production_strong_config_is_allowed():
    settings = Settings(
        environment="production",
        jwt_secret_key="j" * 48,
        git_credentials_secret_key="g" * 48,
        admin_password="strong-admin-password",
        cors_origins="https://shipsmith.internal",
        public_core_url="https://shipsmith.internal",
    )
    validate_runtime_settings(settings)


def test_production_rejects_example_placeholders():
    settings = Settings(
        environment="production",
        jwt_secret_key="replace-with-openssl-rand-base64-48",
        git_credentials_secret_key="replace-with-another-openssl-rand-base64-48",
        admin_password="replace-with-strong-admin-password",
        cors_origins="https://shipsmith.example.com",
        public_core_url="https://shipsmith.example.com",
        database_url="postgresql://shipsmith:replace-with-strong-postgres-password@postgres:5432/shipsmith",
    )

    with pytest.raises(RuntimeError) as exc:
        validate_runtime_settings(settings)

    assert "placeholder" in str(exc.value).lower() or "example.com" in str(exc.value).lower()


def test_production_rejects_wildcard_cors():
    settings = Settings(
        environment="production",
        jwt_secret_key="j" * 48,
        git_credentials_secret_key="g" * 48,
        admin_password="strong-admin-password",
        cors_origins="*",
        public_core_url="https://shipsmith.example.com",
    )

    with pytest.raises(RuntimeError) as exc:
        validate_runtime_settings(settings)

    assert "CORS_ORIGINS" in str(exc.value)

def test_production_allows_loopback_http_public_core_url():
    settings = Settings(
        environment="production",
        jwt_secret_key="j" * 48,
        git_credentials_secret_key="g" * 48,
        admin_password="strong-admin-password",
        cors_origins="http://127.0.0.1:18300",
        public_core_url="http://127.0.0.1:18180",
    )
    validate_runtime_settings(settings)


def test_production_rejects_non_loopback_http_public_core_url():
    settings = Settings(
        environment="production",
        jwt_secret_key="j" * 48,
        git_credentials_secret_key="g" * 48,
        admin_password="strong-admin-password",
        cors_origins="https://shipsmith.internal",
        public_core_url="http://192.168.1.10:8000",
    )
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_settings(settings)

    assert "PUBLIC_CORE_URL" in str(exc.value)
