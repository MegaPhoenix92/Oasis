#!/usr/bin/env python3
"""Validate the Batch 0 scaffold without requiring Unity or cloud credentials."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    ".editorconfig",
    ".env.example",
    ".gitattributes",
    ".github/workflows/ci.yml",
    "assets/README.md",
    "docs/DEV_SETUP.md",
    "docs/LFS_POLICY.md",
    "infrastructure/README.md",
    "src/README.md",
    "src/ai/README.md",
    "src/client/README.md",
    "src/client/.gitignore",
    "src/client/Assets/Scenes/OasisPoC.unity",
    "src/client/Packages/manifest.json",
    "src/client/ProjectSettings/EditorBuildSettings.asset",
    "src/client/ProjectSettings/ProjectSettings.asset",
    "src/client/ProjectSettings/ProjectVersion.txt",
    "src/client/ProjectSettings/TagManager.asset",
    "src/server/README.md",
]

REQUIRED_ENV_KEYS = [
    "ANTHROPIC_API_KEY",
    "MESHY_API_KEY",
    "GCP_PROJECT",
    "GCP_PROJECT_ID",
    "GCP_REGION",
    "FIREBASE_PROJECT_ID",
    "CLOUD_STORAGE_BUCKET",
    "PHOENIX_DATABASE_URL",
    "OASIS_ENV",
    "UNITY_SERVER_PORT",
]

REQUIRED_LFS_PATTERNS = [
    "assets/**/*.glb",
    "assets/**/*.gltf",
    "assets/**/*.bin",
    "assets/**/*.fbx",
    "assets/**/*.png",
    "assets/**/*.jpg",
    "assets/**/*.jpeg",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def check_required_paths() -> None:
    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).is_file()]
    if missing:
        fail("Missing required scaffold files: " + ", ".join(missing))


def check_unity_metadata() -> None:
    manifest = json.loads(read("src/client/Packages/manifest.json"))
    dependencies = manifest.get("dependencies", {})
    if dependencies.get("com.unity.cloud.gltfast") != "6.18.0":
        fail("Unity manifest must pin com.unity.cloud.gltfast to 6.18.0")

    project_version = read("src/client/ProjectSettings/ProjectVersion.txt")
    if "m_EditorVersion: 2022.3.70f1" not in project_version:
        fail("Unity ProjectVersion.txt must pin editor 2022.3.70f1")

    build_settings = read("src/client/ProjectSettings/EditorBuildSettings.asset")
    if "Assets/Scenes/OasisPoC.unity" not in build_settings:
        fail("Unity build settings must include the empty PoC scene")


def check_env_example() -> None:
    env_text = read(".env.example")
    values: dict[str, str] = {}
    for line in env_text.splitlines():
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            fail(f"Invalid .env.example line: {line}")
        key, value = line.split("=", 1)
        values[key] = value

    missing = [key for key in REQUIRED_ENV_KEYS if key not in values]
    if missing:
        fail(".env.example missing keys: " + ", ".join(missing))

    populated = [key for key, value in values.items() if value.strip()]
    if populated:
        fail(".env.example must not contain real or placeholder values: " + ", ".join(populated))


def check_lfs_policy() -> None:
    lines = [line for line in read(".gitattributes").splitlines() if line.strip()]
    patterns = []
    for line in lines:
        pattern, _, attrs = line.partition(" ")
        if not pattern.startswith("assets/"):
            fail(f"LFS pattern must stay under assets/: {pattern}")
        if "filter=lfs" not in attrs or "diff=lfs" not in attrs or "merge=lfs" not in attrs:
            fail(f"LFS pattern missing required attributes: {line}")
        patterns.append(pattern)

    missing = [pattern for pattern in REQUIRED_LFS_PATTERNS if pattern not in patterns]
    if missing:
        fail("Missing LFS patterns: " + ", ".join(missing))


def check_no_binaries_committed() -> None:
    binary_ext = {".glb", ".gltf", ".bin", ".fbx", ".png", ".jpg", ".jpeg"}
    committed_binary_candidates = [
        path
        for path in (ROOT / "assets").rglob("*")
        if path.is_file() and path.suffix.lower() in binary_ext
    ]
    if committed_binary_candidates:
        fail("Batch 0 must not commit asset binaries: " + ", ".join(str(path.relative_to(ROOT)) for path in committed_binary_candidates))


def check_unity_gitignore() -> None:
    ignore_text = read("src/client/.gitignore")
    required_entries = ["/Library/", "/Temp/", "/obj/", "/Build/", "/Logs/", "*.csproj"]
    missing = [entry for entry in required_entries if entry not in ignore_text]
    if missing:
        fail("Unity .gitignore missing entries: " + ", ".join(missing))


def check_markdown_whitespace() -> None:
    markdown_files = [
        path
        for path in ROOT.rglob("*.md")
        if ".git" not in path.parts
    ]
    trailing = []
    for path in markdown_files:
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"[ \t]+$", line):
                trailing.append(f"{path.relative_to(ROOT)}:{index}")
    if trailing:
        fail("Markdown lines contain trailing whitespace: " + ", ".join(trailing))


def main() -> None:
    check_required_paths()
    check_unity_metadata()
    check_env_example()
    check_lfs_policy()
    check_no_binaries_committed()
    check_unity_gitignore()
    check_markdown_whitespace()
    print("Batch 0 scaffold validation passed.")


if __name__ == "__main__":
    main()

