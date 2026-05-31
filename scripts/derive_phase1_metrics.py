#!/usr/bin/env python3
"""Derive Phase-1 Gate 1->2 metrics from local sanitized JSONL inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/ai"))

from oasis_ai.metrics import derive_phase1_metrics, load_telemetry_jsonl, load_user_study_jsonl  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telemetry", type=Path, required=True, help="Path to locked §5 telemetry JSONL")
    parser.add_argument("--user-study", type=Path, help="Optional sanitized user-study hook JSONL")
    args = parser.parse_args()

    telemetry_records = load_telemetry_jsonl(args.telemetry)
    observations = load_user_study_jsonl(args.user_study) if args.user_study else []
    print(json.dumps(derive_phase1_metrics(telemetry_records, observations), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
