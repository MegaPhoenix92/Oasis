from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mock_m4_playable_demo_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_m4_demo.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Mock M4 playable demo validation passed." in result.stdout
    assert '"loop": [' in result.stdout
    assert '"create"' in result.stdout
    assert '"refine_kind": "transform"' in result.stdout
    assert '"ten_minute_script_seconds": 600' in result.stdout

    evidence = json.loads(result.stdout.split("Mock M4 playable demo validation passed.")[0])
    assert evidence["loop"] == ["create", "refine", "voice", "explore", "capture", "save"]
    assert evidence["metrics"]["flow_completion"]["passed"] is True
    assert evidence["metrics"]["asset_quality"]["passed"] is True
    assert evidence["mock_provider_calls"] is False
