# Development Setup

## Required Tools

- Unity `2022.3.70f1` LTS with desktop build support for your platform.
- Git LFS.
- Python 3.11 or newer for scaffold validation and later AI tooling.
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

   Keep values empty until you have approved development credentials. Runtime code added in later batches should fail fast when a required variable is missing, empty, or still set to a placeholder.

3. Open the Unity project from `src/client` in Unity `2022.3.70f1`.

4. Run the lightweight scaffold checks locally:

   ```sh
   python3 scripts/validate_scaffold.py
   ```

## Notes

- Batch 0 does not build the Unity player in CI. The first CI gate validates metadata and repository hygiene only.
- The root `assets/` directory is reserved for generated/imported meshes and textures and is covered by Git LFS policy.
- The Unity project starts with an empty scene and no gameplay code.

