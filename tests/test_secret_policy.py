from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_secret_scan_workflow_runs_gitleaks_and_fails_on_findings() -> None:
    workflow = (ROOT / ".github/workflows/secret-scan.yml").read_text(encoding="utf-8")
    validator = (ROOT / "scripts/validate_secret_scanning.py").read_text(encoding="utf-8")

    assert "gitleaks/gitleaks-action" in workflow
    assert "GITLEAKS_CONFIG: .gitleaks.toml" in workflow
    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "--exit-code" in validator
    assert "secrets.token_hex(32)" in validator
    assert 'api_key = "{secret_value}"' in validator


def test_env_example_is_names_only_for_secret_scan() -> None:
    content = (ROOT / ".env.example").read_text(encoding="utf-8")

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert "=" in stripped
        name, value = stripped.split("=", 1)
        assert name
        assert value == ""


def test_e2e_strategy_documents_mock_boundary_and_secret_policy() -> None:
    doc = (ROOT / "docs/testing/e2e-test-strategy-and-secrets-policy.md").read_text(encoding="utf-8")

    assert "mock-only" in doc
    assert "Golden-prompt acceptance" in doc
    assert "server-side only" in doc
    assert ".env.example" in doc
    assert "Gitleaks" in doc
    assert "0002" in doc
