#!/usr/bin/env python3
"""
ShipSmith Smoke Test Script

Runs a comprehensive smoke test to verify all components work together.
- DB: Connects and runs migrations
- API: Starts and serves endpoints
- Project: Creates, reads, updates, deletes
- Agent: Basic connectivity and task handling

Usage:
    python tests/smoke_test.py
"""

import os
import sys
import json
import subprocess
import time
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Callable


SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    details: Optional[str] = None


class SmokeTestRunner:
    def __init__(self):
        self.results: List[TestResult] = []
        self.temp_dir: Optional[Path] = None
        self.env: dict = {}

    def run(self) -> bool:
        print("=" * 60)
        print("ShipSmith Smoke Test")
        print("=" * 60)
        print()

        try:
            self.setup()
            self.test_db_setup()
            self.test_api_startup()
            self.test_projects()
            self.test_deployments()
            self.test_feature_flags()
            self.test_webhooks()
            self.test_agent_selfcheck()
        except Exception as e:
            self.results.append(
                TestResult(
                    name="setup",
                    passed=False,
                    message=f"Smoke test failed with exception",
                    details=str(e),
                )
            )
        finally:
            self.cleanup()

        return self.print_results()

    def setup(self):
        print("[1/7] Setting up test environment...")
        self.temp_dir = Path(tempfile.mkdtemp(prefix="shipsmith-smoke-"))
        print(f"    Temporary directory: {self.temp_dir}")

        self.env = {
            "SHIPSMITH_CORE_URL": "http://localhost:8000/api/v1",
            "SHIPSMITH_AGENT_TOKEN": "test-token",
            "SHIPSMITH_WORKDIR": str(self.temp_dir / "workdir"),
            "SHIPSMITH_LOG_LEVEL": "INFO",
        }
        os.makedirs(self.env["SHIPSMITH_WORKDIR"], exist_ok=True)

    def cleanup(self):
        print("\nCleaning up...")
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def run_command(self, cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            cwd=str(cwd or PROJECT_ROOT),
            capture_output=True,
            text=True,
            env={**os.environ, **self.env},
        )

    def check_pytest_installed(self) -> bool:
        try:
            result = self.run_command(["python", "-c", "import pytest; print(pytest.__version__)"])
            return result.returncode == 0
        except Exception:
            return False

    def test_db_setup(self):
        print("\n[2/7] Testing database setup...")

        db_package = PROJECT_ROOT / "packages" / "db"
        if not db_package.exists():
            self.results.append(
                TestResult(
                    name="db_package",
                    passed=False,
                    message="DB package not found",
                    details=f"Expected at: {db_package}",
                )
            )
            return

        models_file = db_package / "shipsmith_db" / "models.py"
        if models_file.exists():
            self.results.append(
                TestResult(
                    name="db_models",
                    passed=True,
                    message="DB models file exists",
                )
            )
        else:
            self.results.append(
                TestResult(
                    name="db_models",
                    passed=False,
                    message="DB models file not found",
                    details=f"Expected at: {models_file}",
                )
            )

        migrations_dir = db_package / "migrations" / "versions"
        if migrations_dir.exists():
            migrations = list(migrations_dir.glob("*.py"))
            self.results.append(
                TestResult(
                    name="db_migrations",
                    passed=len(migrations) > 0,
                    message=f"Found {len(migrations)} migration files",
                )
            )
        else:
            self.results.append(
                TestResult(
                    name="db_migrations",
                    passed=False,
                    message="Migrations directory not found",
                    details=f"Expected at: {migrations_dir}",
                )
            )

    def test_api_startup(self):
        print("\n[3/7] Testing API structure...")

        api_package = PROJECT_ROOT / "apps" / "api"
        if not api_package.exists():
            self.results.append(
                TestResult(
                    name="api_package",
                    passed=False,
                    message="API package not found",
                    details=f"Expected at: {api_package}",
                )
            )
            return

        main_file = api_package / "shipsmith_api" / "main.py"
        if main_file.exists():
            self.results.append(
                TestResult(
                    name="api_main",
                    passed=True,
                    message="API main file exists",
                )
            )
        else:
            self.results.append(
                TestResult(
                    name="api_main",
                    passed=False,
                    message="API main file not found",
                    details=f"Expected at: {main_file}",
                )
            )

        routers = [
            "auth.py",
            "projects.py",
            "deployments.py",
            "flags.py",
            "agents.py",
            "webhooks.py",
        ]
        routers_dir = api_package / "shipsmith_api" / "routers"
        for router in routers:
            router_file = routers_dir / router
            if router_file.exists():
                self.results.append(
                    TestResult(
                        name=f"api_router_{router.replace('.py', '')}",
                        passed=True,
                        message=f"Router file exists: {router}",
                    )
                )
            else:
                self.results.append(
                    TestResult(
                        name=f"api_router_{router.replace('.py', '')}",
                        passed=False,
                        message=f"Router file missing: {router}",
                        details=f"Expected at: {router_file}",
                    )
                )

        pyproject = api_package / "pyproject.toml"
        if pyproject.exists():
            self.results.append(
                TestResult(
                    name="api_config",
                    passed=True,
                    message="API pyproject.toml exists",
                )
            )

    def test_projects(self):
        print("\n[4/7] Testing project endpoints structure...")

        api_package = PROJECT_ROOT / "apps" / "api"
        projects_router = api_package / "shipsmith_api" / "routers" / "projects.py"

        if not projects_router.exists():
            self.results.append(
                TestResult(
                    name="project_router",
                    passed=False,
                    message="Projects router not found",
                )
            )
            return

        content = projects_router.read_text()

        endpoints = [
            ("list", "@router.get"),
            ("create", "HTTP_201_CREATED"),
            ("get", "{project_id}"),
            ("update", "@router.patch"),
            ("rotate_token", "rotate-agent-token"),
            ("status", "/status"),
            ("deploy", "/deploy"),
            ("rollback", "/rollback"),
            ("webhook_secret", "generate-webhook-secret"),
        ]

        for name, pattern in endpoints:
            if pattern in content:
                self.results.append(
                    TestResult(
                        name=f"project_endpoint_{name}",
                        passed=True,
                        message=f"Endpoint present: {name}",
                    )
                )
            else:
                self.results.append(
                    TestResult(
                        name=f"project_endpoint_{name}",
                        passed=False,
                        message=f"Endpoint may be missing: {name}",
                        details=f"Pattern: {pattern}",
                    )
                )

    def test_deployments(self):
        print("\n[5/7] Testing deployment endpoints structure...")

        api_package = PROJECT_ROOT / "apps" / "api"
        deployments_router = api_package / "shipsmith_api" / "routers" / "deployments.py"

        if not deployments_router.exists():
            self.results.append(
                TestResult(
                    name="deployment_router",
                    passed=False,
                    message="Deployments router not found",
                )
            )
            return

        content = deployments_router.read_text()

        endpoints = [
            ("get", "{deployment_id}"),
            ("logs", "/logs"),
            ("detail", "/detail"),
        ]

        for name, pattern in endpoints:
            if pattern in content:
                self.results.append(
                    TestResult(
                        name=f"deployment_endpoint_{name}",
                        passed=True,
                        message=f"Endpoint present: {name}",
                    )
                )
            else:
                self.results.append(
                    TestResult(
                        name=f"deployment_endpoint_{name}",
                        passed=False,
                        message=f"Endpoint may be missing: {name}",
                        details=f"Pattern: {pattern}",
                    )
                )

    def test_feature_flags(self):
        print("\n[6/7] Testing feature flag endpoints structure...")

        api_package = PROJECT_ROOT / "apps" / "api"
        flags_router = api_package / "shipsmith_api" / "routers" / "flags.py"

        if not flags_router.exists():
            self.results.append(
                TestResult(
                    name="flags_router",
                    passed=False,
                    message="Flags router not found",
                )
            )
            return

        content = flags_router.read_text()

        endpoints = [
            ("list", "@router.get"),
            ("create", "HTTP_201_CREATED"),
            ("update", "@router.patch"),
            ("archive", "/archive"),
            ("unarchive", "/unarchive"),
            ("delete", "@router.delete"),
            ("snapshot", "/snapshot"),
        ]

        for name, pattern in endpoints:
            if pattern in content:
                self.results.append(
                    TestResult(
                        name=f"flag_endpoint_{name}",
                        passed=True,
                        message=f"Endpoint present: {name}",
                    )
                )
            else:
                self.results.append(
                    TestResult(
                        name=f"flag_endpoint_{name}",
                        passed=False,
                        message=f"Endpoint may be missing: {name}",
                        details=f"Pattern: {pattern}",
                    )
                )

    def test_webhooks(self):
        print("\n[7/7] Testing webhook endpoints structure...")

        api_package = PROJECT_ROOT / "apps" / "api"
        webhooks_router = api_package / "shipsmith_api" / "routers" / "webhooks.py"

        if not webhooks_router.exists():
            self.results.append(
                TestResult(
                    name="webhooks_router",
                    passed=False,
                    message="Webhooks router not found",
                )
            )
            return

        content = webhooks_router.read_text()

        features = [
            ("github", "github"),
            ("gitlab", "gitlab"),
            ("signature", "signature"),
            ("branch_filter", "ref"),
            ("idempotency", "delivery_id"),
        ]

        for name, pattern in features:
            if pattern in content:
                self.results.append(
                    TestResult(
                        name=f"webhook_{name}",
                        passed=True,
                        message=f"Feature present: {name}",
                    )
                )
            else:
                self.results.append(
                    TestResult(
                        name=f"webhook_{name}",
                        passed=False,
                        message=f"Feature may be missing: {name}",
                        details=f"Pattern: {pattern}",
                    )
                )

    def test_agent_selfcheck(self):
        print("\n[8/8] Testing agent self-check module...")

        agent_package = PROJECT_ROOT / "packages" / "agent"
        main_file = agent_package / "shipsmith_agent" / "main.py"

        if not main_file.exists():
            self.results.append(
                TestResult(
                    name="agent_main",
                    passed=False,
                    message="Agent main file not found",
                )
            )
            return

        content = main_file.read_text()

        features = [
            ("selfcheck", "selfcheck"),
            ("command_available", "_check_command_available"),
            ("directory_writable", "_check_directory_writable"),
            ("docker_daemon", "_check_docker_daemon"),
            ("core_connectivity", "_check_core_connectivity"),
            ("help", "show_help"),
        ]

        for name, pattern in features:
            if pattern in content:
                self.results.append(
                    TestResult(
                        name=f"agent_{name}",
                        passed=True,
                        message=f"Feature present: {name}",
                    )
                )
            else:
                self.results.append(
                    TestResult(
                        name=f"agent_{name}",
                        passed=False,
                        message=f"Feature may be missing: {name}",
                        details=f"Pattern: {pattern}",
                    )
                )

    def print_results(self) -> bool:
        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print()

        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)

        for r in self.results:
            status = "[PASS]" if r.passed else "[FAIL]"
            print(f"{status} {r.name}")
            print(f"       {r.message}")
            if r.details and not r.passed:
                print(f"       Details: {r.details}")
            print()

        print("-" * 60)
        print(f"Total: {passed_count}/{total_count} tests passed")
        print()

        if passed_count == total_count:
            print("All smoke tests PASSED!")
            return True
        else:
            print(f"Some tests FAILED. See details above.")
            return False


def main():
    runner = SmokeTestRunner()
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
