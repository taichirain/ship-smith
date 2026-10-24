import os
import sys
from datetime import datetime

import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "packages",
        "db",
    ),
)
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "packages",
        "config",
    ),
)

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session
from shipsmith_db import Base, Project, ProjectStatus, ProjectTarget, Deployment, FeatureFlag, User
from shipsmith_api.main import create_app
from fastapi.testclient import TestClient


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def test_session(test_engine):
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(test_session: Session):
    from shipsmith_api.security import hash_password as get_password_hash

    user = User(
        username="testuser",
        password_hash=get_password_hash("testpassword"),
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture
def test_project(test_session: Session):
    project = Project(
        name="test-project",
        git_repo="https://github.com/test/repo.git",
        git_branch="main",
        git_credential_type="none",
        deploy_workdir="/opt/test",
        compose_file="docker-compose.yml",
        compose_service="app",
        app_services=["app"],
        deploy_strategy="compose-build",
        healthcheck_url="http://localhost:8080/health",
        healthcheck_timeout_seconds=10,
        flags_file_path="/opt/test/flags.json",
        agent_id="agent-test-123",
        agent_token_hash="test-hash",
        webhook_endpoint_id="wh-test-123",
    )
    test_session.add(project)
    test_session.flush()

    project_status = ProjectStatus(
        project_id=project.id,
        health_status="healthy",
    )
    test_session.add(project_status)

    project_target = ProjectTarget(
        project_id=project.id,
        agent_id=project.agent_id,
        name=f"{project.name}-default",
        role="primary",
        enabled=True,
        order_index=0,
    )
    test_session.add(project_target)
    test_session.commit()
    test_session.refresh(project)
    return project


@pytest.fixture
def test_deployment(test_session: Session, test_project: Project):
    deployment = Deployment(
        project_id=test_project.id,
        kind="deploy",
        status="success",
        trigger_source="manual",
        commit_hash="abc123def456",
        triggered_by="testuser",
        queued_at=datetime(2026, 1, 1, 0, 0, 0),
        started_at=datetime(2026, 1, 1, 0, 1, 0),
        finished_at=datetime(2026, 1, 1, 0, 5, 0),
    )
    test_session.add(deployment)
    test_session.commit()
    test_session.refresh(deployment)
    return deployment


@pytest.fixture
def test_feature_flag(test_session: Session, test_project: Project):
    flag = FeatureFlag(
        project_id=test_project.id,
        key="test_feature",
        enabled=True,
        description="Test feature flag",
        version=1,
        updated_by="testuser",
    )
    test_session.add(flag)
    test_session.commit()
    test_session.refresh(flag)
    return flag


@pytest.fixture
def client(test_session: Session):
    app = create_app(start_monitor=False)

    def override_get_db():
        try:
            yield test_session
        finally:
            pass

    from shipsmith_api import deps

    app.dependency_overrides[deps.get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client: TestClient, test_user: User):
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "testpassword",
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
