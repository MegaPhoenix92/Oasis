# M1 Data Contracts & Pipeline Architecture

**Document:** 0002
**Date:** 2026-05-30
**Status:** Accepted — **LOCKED** for the M1 build batch (#5, #6, #7, #8, #9)
**Related:** [ADR-0001](adr/0001-engine.md) (engine = Unity), `../ROADMAP.md`, `../scope/MVP_SCOPE_DOCUMENT.md`, issues #5/#6/#7/#8/#9/#24

---

## Purpose

This is the single locked contract every M1 builder conforms to. It exists so the
text → spec → asset → scene flow composes at integration (#9) instead of each issue
inventing its own schema. **Do not diverge from the schemas or the architecture
decision below without updating this doc first.** If a schema looks wrong while
building, STOP and flag it — do not silently work around it.

---

## 1. Architecture decision — where the pipeline runs

**Decision:** the AI generation pipeline runs as a **backend HTTP service**, not in the
Unity client. API keys live **server-side only**.

| Aspect | Locked choice |
|--------|---------------|
| Location | `src/ai/` (the AI integration service) |
| Language / runtime | Python 3.11 (matches CI + `scripts/validate_scaffold.py`) |
| Framework / tooling | FastAPI + `uv`; `anthropic` SDK for Claude; `httpx` for Meshy REST |
| Client → service | Unity client (#8) calls the service over HTTP (localhost in PoC) |
| Secrets | `ANTHROPIC_API_KEY`, `MESHY_API_KEY` read from env (`.env.example` names). **Never** shipped in the client, committed, or logged. |

**Why:** keeps keys out of the client binary (matches Gate 0 "no secret in client-side
committed config" and `ARCHITECTURE_OVERVIEW.md` — the *server* calls Claude, not the
client), and lets #5/#6 be unit-tested and run against the golden-prompt suite (#73)
without launching Unity. The dedicated game server (`src/server/`) — world state /
persistence — is a Phase-2 concern; for M1 the only backend is this `src/ai` service.

### Endpoints

| Method / path | Issue | Input | Output |
|---------------|-------|-------|--------|
| `POST /spec` | #5 | `{ "prompt": "<text>" }` | `Spec` (§2) |
| `POST /generate` | #6 | `Spec` (§2) | `AssetManifest` (§4) + a way to fetch the glTF |
| `POST /create` | #9 | `{ "prompt": "<text>" }` | chains /spec → /generate; returns `AssetManifest` + glTF URL |
| `GET /healthz` | — | — | liveness for CI/local checks |

---

## 2. Schema — prompt → structured spec (#5 output, #6 input)

Extends the schema in issue #5 with a `schema_version` and an explicit `meshy_prompt`
(the refined natural-language string that bridges spec → Meshy, §3).

```json
{
  "schema_version": "1.0",
  "object_type": "furniture",
  "name": "wooden chair",
  "materials": ["wood", "fabric"],
  "style": "medieval",
  "dimensions": { "width": 0.5, "height": 1.0, "depth": 0.5 },
  "details": ["carved armrests", "high back"],
  "meshy_prompt": "a medieval wooden chair with carved armrests and a high back, fabric seat"
}
```

Rules:
- `schema_version` is required; bump it (and this doc) on any breaking field change.
- `dimensions` are meters. `materials`/`details` are free-form lists.
- `meshy_prompt` is **the** field #6 consumes — #5 owns producing a clean one.
- #5 must validate the model's JSON against this shape and repair-or-typed-error on
  malformed output. Do not pass un-validated model text downstream.

---

## 3. Mapping — spec → Meshy request (#6)

Meshy `text-to-3d` (PoC defaults):

| Meshy param | Source |
|-------------|--------|
| `prompt` | `spec.meshy_prompt` |
| `art_style` | derived from `spec.style` (e.g. `realistic` / `sculpture`) |
| `mode` | `preview` for M1 (fast); `refine` deferred |
| `target_polycount` | PoC default (medium); may be informed by `spec.dimensions` |
| output `format` | glTF 2.0 / `glb` |

`#3` (3D-API evaluation) already recommends Meshy; #6 implements it and records a cost
projection. **Spend control:** #6 must cap/guard generation calls (per-run ceiling) so a
loop can't run up Meshy cost — the one acute Phase-1 risk from the threat-model discussion.

---

## 4. Schema — asset manifest / provenance (#7, folded-in)

Every generated asset carries a manifest. It travels with local save/load (#19) and
export (#20).

```json
{
  "asset_id": "uuid-v4",
  "source_prompt": "a wooden chair",
  "normalized_prompt": "wooden chair",
  "spec": { "...": "the §2 Spec that produced it" },
  "provider": "meshy.ai",
  "job_id": "<provider job id>",
  "source_url": "<provider asset url>",
  "checksum_sha256": "<hex>",
  "format": "glb",
  "file_size_bytes": 123456,
  "triangle_count": 12345,
  "texture_count": 2,
  "created_at": "2026-05-30T00:00:00Z"
}
```

Import rules (#7): reject unsupported formats, oversized files, or assets missing
required manifest fields; a malformed/oversized asset must fail gracefully and **never
crash the scene** (testable via the offline fixture, #74).

---

## 5. End-to-end flow & telemetry (#9, #24)

The #9 flow: `prompt → /spec → /generate → download glTF → import → preview → place`.

Telemetry events (the #24 fold-in) — emitted by the service and client, keyed by
`session_id` + `prompt_id`:

```
prompt_submitted · prompt_structured · generation_submitted · generation_ready
· asset_downloaded · asset_imported · object_placed · flow_failed
```

Standard fields per event: `session_id`, `prompt_id`, `provider`, `elapsed_ms`,
`error_code`, `asset_id`. Phase-1 sink = local JSONL. These feed the Gate 1→2 metrics
and the golden-prompt suite (#73).

**Performance budget (#9):** Claude < 5s · Meshy < 60s · import < 5s · **total < 90s**,
working ≥ 80% of the time.

---

## 6. Error model

Typed errors, mapped to HTTP status:

| Error | When | HTTP |
|-------|------|------|
| `invalid_prompt` | empty / unusable prompt | 400 |
| `model_parse_error` | Claude output not schema-valid after repair | 502 |
| `provider_error` | Meshy/Claude API failure | 502 |
| `timeout` | stage exceeds its budget | 504 |

Errors emit `flow_failed` with the `error_code`.

---

## 7. Security invariants (hold for every M1 PR)

1. `ANTHROPIC_API_KEY` / `MESHY_API_KEY` are read from env, **server-side only** — never
   in the client, never committed, never logged.
2. No secret value appears in any committed file (`.env.example` carries names only).
3. Meshy generation has a per-run spend guard.
4. #5/#6 are **security-shape** PRs → merge gate is **≥ 2 NON-xAI lineages** APPROVE.

---

*LOCKED for M1. Any change lands here first, then in the affected issues.*
