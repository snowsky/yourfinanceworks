"""Maintained deployment variants must not publish unauthenticated admin UIs."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("filename", ["docker-compose.yml", "docker-compose-quay.yml"])
def test_api_defaults_override_stale_debug_env_file(filename):
    services = yaml.safe_load((ROOT / filename).read_text())["services"]
    environment = dict(item.split("=", 1) for item in services["api"]["environment"])
    assert environment.get("DEBUG", "").lower() == "false"
    assert environment.get("ENVIRONMENT") == "production"


@pytest.mark.parametrize("filename", ["docker-compose.yml", "docker-compose-quay.yml"])
@pytest.mark.parametrize("name,port", [("kafdrop", 9000), ("opensearch-dashboards", 5601)])
def test_management_uis_require_opt_in_and_loopback(filename, name, port):
    service = yaml.safe_load((ROOT / filename).read_text())["services"][name]
    assert service["ports"] == [f"127.0.0.1:{port}:{port}"]
    assert "admin" in service.get("profiles", [])
