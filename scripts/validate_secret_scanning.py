from __future__ import annotations

import shutil
import secrets
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    gitleaks = shutil.which("gitleaks")
    if gitleaks is None:
        print("gitleaks is not installed; install it to run the local secret-scan validator.")
        return 2

    repo_scan = subprocess.run(
        [gitleaks, "detect", "--source", str(ROOT), "--no-git", "--redact", "--exit-code", "1", "--config", str(ROOT / ".gitleaks.toml")],
        text=True,
        capture_output=True,
        check=False,
    )
    if repo_scan.returncode != 0:
        print(repo_scan.stdout)
        print(repo_scan.stderr)
        return repo_scan.returncode

    with tempfile.TemporaryDirectory() as temp_root:
        probe = Path(temp_root)
        (probe / ".env.example").write_text("ANTHROPIC_API_KEY=\nMESHY_API_KEY=\n", encoding="utf-8")
        clean = subprocess.run(
            [gitleaks, "detect", "--source", str(probe), "--no-git", "--redact", "--exit-code", "1", "--config", str(ROOT / ".gitleaks.toml")],
            text=True,
            capture_output=True,
            check=False,
        )
        if clean.returncode != 0:
            print(clean.stdout)
            print(clean.stderr)
            return clean.returncode

        secret_value = secrets.token_hex(32)
        (probe / "leak.txt").write_text(f'api_key = "{secret_value}"\n', encoding="utf-8")
        planted = subprocess.run(
            [gitleaks, "detect", "--source", str(probe), "--no-git", "--redact", "--exit-code", "1", "--config", str(ROOT / ".gitleaks.toml")],
            text=True,
            capture_output=True,
            check=False,
        )
        if planted.returncode != 1:
            print(planted.stdout)
            print(planted.stderr)
            print("expected gitleaks to fail on the planted generated test secret")
            return 1

    print("secret scanning validator passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
