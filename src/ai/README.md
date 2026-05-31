# AI Integration

Python 3.11 FastAPI service for the Phase 1 AI pipeline. Issue #5 implements
`POST /spec`, which converts a raw text prompt into the locked M1 `Spec` JSON
contract in `docs/architecture/0002-m1-data-contracts.md`. Issue #6 adds
Meshy-backed asset generation:

- `POST /generate` accepts a locked `Spec` and returns a pending `job_id`
  immediately.
- `GET /jobs/{job_id}` polls Meshy server-side and returns a ready manifest or
  typed failure.
- `GET /assets/{asset_id}` serves only cached GLB bytes from
  `assets/generated/{asset_id}.glb`.

Run locally:

```bash
uv run uvicorn oasis_ai.app:app --app-dir src/ai --reload
```

Run tests:

```bash
uv run --extra test pytest -q
```

`ANTHROPIC_API_KEY` and `MESHY_API_KEY` are read from the server environment
only. Tests mock Claude and Meshy, and do not require or use live API keys.
Live Meshy generation is opt-in by configuring `MESHY_API_KEY`; use
`OASIS_MESHY_MAX_GENERATIONS` to lower the per-process generation call guard
from its default of 5.
