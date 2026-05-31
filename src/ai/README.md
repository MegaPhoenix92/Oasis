# AI Integration

Python 3.11 FastAPI service for the Phase 1 AI pipeline. Issue #5 implements
`POST /spec`, which converts a raw text prompt into the locked M1 `Spec` JSON
contract in `docs/architecture/0002-m1-data-contracts.md`.

Run locally:

```bash
uv run uvicorn oasis_ai.app:app --app-dir src/ai --reload
```

Run tests:

```bash
uv run --extra test pytest -q
```

`ANTHROPIC_API_KEY` is read from the server environment only. Tests mock Claude
and do not require or use a live API key.
