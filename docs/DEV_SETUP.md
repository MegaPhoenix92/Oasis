# Development Setup

## Required Tools

- Unity `2022.3.70f1` LTS with desktop build support for your platform.
- Git LFS.
- Python 3.11 (the AI service pins `>=3.11,<3.12`) plus [uv](https://docs.astral.sh/uv/) for dependency management.
- Node.js 20 or newer for future repository tooling.

## First-Time Setup

1. Install Git LFS and enable it:

   ```sh
   git lfs install
   ```

2. Copy the environment template:

   ```sh
   cp .env.example .env
   ```

   Keep values empty until you have approved development credentials. Runtime
   code fails fast when a required variable is missing, empty, or still set to
   a placeholder. No secret is ever required by — or committed to — the Unity
   client; provider keys live server-side only (see
   `docs/testing/e2e-test-strategy-and-secrets-policy.md`).

3. Open the Unity project from `src/client` in Unity `2022.3.70f1`.

4. Run the offline validation suite locally:

   ```sh
   python3 scripts/validate_scaffold.py
   python3 scripts/validate_unity_import_pipeline.py
   python3 scripts/validate_unity_creator_ui.py
   python3 scripts/build_import_fixture.py --check
   uv run --extra test pytest -q
   ```

## Unity project

The client lives in `src/client` (scene `Assets/Scenes/OasisPoC.unity`). On
first open, Unity resolves the packages pinned in `src/client/Packages/manifest.json`:

| Package | Version | Why |
|---------|---------|-----|
| `com.unity.cloud.gltfast` | 6.18.0 | Runtime glTF/GLB import (the #7 import pipeline) |
| `com.unity.test-framework` | 1.1.33 | Edit/Play-mode test harness (C# behavioral coverage — #88) |
| `com.unity.textmeshpro` | 3.0.6 | Creator UI text rendering |
| `com.unity.ugui` | 1.0.0 | Creator UI canvas |
| `com.unity.timeline`, IDE & development packages | pinned | Editor tooling |

Verify after opening: no package-resolution errors in the console, and
`GLTFast` resolves in `Assets/Scripts/Oasis/Import/OasisGlbImporter.cs`.

The client scripts under `Assets/Scripts/Oasis/` implement the Phase-1 PoC:
asset import & placement (`Import/`), creator UI and generation facade
(`UI/`), world persistence, history, and the World Document (`Persistence/`),
first-person exploration, time-of-day, and scene bootstrap (`Scene/`), and
screenshot/clip capture (`Capture/`).

## Continuous integration

CI (`.github/workflows/ci.yml`) runs on every pull request:

- scaffold, import-pipeline, creator-UI, and offline-fixture validators;
- the mocked AI-service pytest suite (`uv run --extra test pytest -q`) — no
  network, no provider keys;
- secret scanning (`.github/workflows/secret-scan.yml`).

CI does not build the Unity player or run C# tests yet; a Unity/NUnit
behavioral harness is tracked in issue #88. Golden-prompt acceptance
(`tests/test_golden_prompts.py`) runs in the pytest job; the M4 demo
validator (`scripts/validate_m4_demo.py`) is exercised through
`tests/test_m4_demo.py`.

## Notes

- The root `assets/` directory is reserved for generated/imported meshes and
  textures and is covered by Git LFS policy (`docs/LFS_POLICY.md`). Test
  fixtures are committed as text (see `tests/fixtures/unity_import/README.md`).
