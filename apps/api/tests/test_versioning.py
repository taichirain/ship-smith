"""Release versioning: build-stamped versions and wheel URL derivation."""
from types import SimpleNamespace

from shipsmith_api import __version__ as API_VERSION
from shipsmith_api.routers.projects import _agent_wheel_url, _is_version_outdated


def test_same_semver_different_sha_is_outdated():
    assert _is_version_outdated("0.1.0+aaa1111", "0.1.0+bbb2222") is True


def test_same_build_is_not_outdated():
    assert _is_version_outdated("0.1.0+aaa1111", "0.1.0+aaa1111") is False


def test_older_semver_is_outdated():
    assert _is_version_outdated("0.0.9+zzz9999", "0.1.0+aaa1111") is True


def test_newer_agent_semver_is_not_outdated():
    assert _is_version_outdated("0.2.0", "0.1.0+aaa1111") is False


def test_missing_agent_version_is_outdated():
    assert _is_version_outdated(None, "0.1.0+aaa1111") is True


def test_wheel_url_derived_from_install_script_url():
    settings = SimpleNamespace(
        agent_wheel_url="",
        install_script_url="http://127.0.0.1:18300/install.sh",
    )
    url = _agent_wheel_url(settings)
    assert url == f"http://127.0.0.1:18300/downloads/shipsmith_agent-{API_VERSION}-py3-none-any.whl"


def test_wheel_url_explicit_override_wins():
    settings = SimpleNamespace(
        agent_wheel_url="https://mirror.internal/agent.whl",
        install_script_url="http://127.0.0.1:18300/install.sh",
    )
    assert _agent_wheel_url(settings) == "https://mirror.internal/agent.whl"


def test_wheel_url_empty_for_placeholder_install_script():
    settings = SimpleNamespace(
        agent_wheel_url="",
        install_script_url="https://shipsmith.example.com/install.sh",
    )
    assert _agent_wheel_url(settings) == ""