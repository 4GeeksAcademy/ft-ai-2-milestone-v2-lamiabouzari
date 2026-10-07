"""Static checks for hardening committed in the repository.

These do not prove a live server. They only prove the files operators
are expected to deploy.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_compose_does_not_publish_internal_services_on_all_interfaces():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "127.0.0.1:6379:6379" in compose
    assert "127.0.0.1:6333:6333" in compose
    assert "127.0.0.1:6334:6334" in compose
    assert "127.0.0.1:5555:5555" in compose
    assert '"6379:6379"' not in compose
    assert '"5555:5555"' not in compose


def test_backend_image_drops_reload_and_runs_as_trackflow():
    dockerfile = (ROOT / "services" / "Dockerfile").read_text(encoding="utf-8")
    assert "--reload" not in dockerfile
    assert "USER trackflow" in dockerfile
    assert "uid 10001" in dockerfile


def test_hardening_runbook_disables_root_ssh():
    runbook = (ROOT / "docs" / "security" / "server-hardening.md").read_text(encoding="utf-8")
    assert "PermitRootLogin no" in runbook
    assert "deployment verification" in runbook.lower()
