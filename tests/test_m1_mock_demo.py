from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mock_m1_demo_validator_passes_under_budget() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_m1_mock_demo.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert '"prompt": "a wooden treasure chest"' in result.stdout
    assert '"fetch_path": "/assets/' in result.stdout
    assert '"live_provider_calls": false' in result.stdout
    assert "Mock M1 prompt-to-object demo validation passed." in result.stdout
