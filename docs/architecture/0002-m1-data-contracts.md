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
| Claude model | Sonnet tier (e.g. `claude-sonnet-4-6`) or Haiku for the < 5s budget — **NOT Opus** |
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
| `POST /generate` | #6 | `Spec` (§2) | `{ "job_id": "...", "status": "pending" }` — **async**, does not block on Meshy |
| `GET /jobs/{job_id}` | #6 | `job_id` | `{ "status": "pending\|processing\|ready\|failed", "manifest"?, "error_code"? }` |
| `GET /assets/{asset_id}` | #6/#7 | `asset_id` | the cached glTF binary — **the client's only fetch path** |
| `POST /create` | #9 | `{ "prompt": "<text>" }` | convenience: submits the chained flow, returns `{ job_id, status }`; client polls `/jobs/{id}` |
| `GET /healthz` | — | — | liveness for CI/local checks |

**Async model (LOCKED):** `/generate` and `/create` submit the Meshy job and return a
`job_id` **immediately** — they do **not** hold the HTTP socket open across Meshy's ~60s
generation (so no long client/server timeout config is needed, and #8's "Generating"
state has something to poll). The client polls `GET /jobs/{job_id}` (~2s interval) until
`ready` (with `manifest`) or `failed` (with `error_code`), giving up at the §5 budget
(> 90s total → `timeout`).

### Asset delivery — how the glTF binary reaches the client (LOCKED)

The binary path is part of the contract, not a builder choice:

1. `/generate` (#6) downloads the glTF from Meshy **server-side**, writes it to a local
   cache (`assets/generated/{asset_id}.glb`), computes the checksum, and records both the
   cache path and the canonical fetch endpoint in the manifest.
2. The Unity client (#8/#9) fetches the binary **only** via `GET /assets/{asset_id}` —
   **never** from `source_url`, and **never** by reading a server filesystem path.
   `local_path` (§4) is backend-internal bookkeeping, not a client contract.
3. **Ruled out:** the client fetching Meshy's `source_url`. Those URLs are
   time-limited/signed, so a saved world (#19) would reload to dead links, and it would
   risk leaking the Meshy key to the client. `source_url` is **provenance only**.

---

## 2. Schema — prompt → structured spec (#5 output, #6 input)

Extends the schema in issue #5 with a `schema_version` and an explicit `meshy_prompt`
(the refined natural-language string that bridges spec → Meshy, §3).

```json
{
  "schema_version": "1.0",
  "source_prompt": "a wooden chair",
  "normalized_prompt": "wooden chair",
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
- `source_prompt` = the raw user input verbatim; `normalized_prompt` = lowercased,
  trimmed, whitespace-collapsed. Both are carried in the Spec so #6 fills the matching
  manifest fields (§4) **deterministically** — #6 does not re-derive them.
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
  "source_url": "<provider asset url — PROVENANCE ONLY, may expire, never the client fetch path>",
  "fetch_path": "/assets/<asset_id>",
  "local_path": "assets/generated/<asset_id>.glb",
  "checksum_sha256": "<hex>",
  "format": "glb",
  "file_size_bytes": 123456,
  "triangle_count": 12345,
  "texture_count": 2,
  "created_at": "2026-05-30T00:00:00Z"
}
```

- `fetch_path` (the `/assets/{id}` endpoint) is the **only** client-facing way to get the
  binary. `local_path` is **backend-internal** (server cache bookkeeping), resolved
  relative to the repo root — not a client contract. `source_url` is provenance only
  (see §1 Asset delivery).
- The cached binary + manifest (not `source_url`) are what persist for save/load (#19)
  and export (#20); the server cache is ephemeral — see the persistence invariant in §7.

Import rules (#7): reject unsupported formats, oversized files, or assets missing
required manifest fields; a malformed/oversized asset must fail gracefully and **never
crash the scene** (testable via the offline fixture, #74).

### Import & placement semantics (#7/#9 — LOCKED so both import identically)

- **Up-axis / handedness:** assets are glTF 2.0 (+Y up, right-handed); rely on glTFast's
  standard glTF→Unity conversion — do **not** apply an extra axis flip.
- **Scale:** normalize on import — uniformly scale the mesh so its bounding box matches
  `spec.dimensions` (meters), preserving aspect ratio (fit, don't stretch).
- **Pivot / origin:** ground the object — pivot at the bottom-center of the bounding box,
  so it sits on the surface rather than half-buried.
- **Placement anchor:** positioned at the user's click point on the ground plane (#7),
  resting on it.

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

#24 extends this contract without adding telemetry event names or raw payload fields:
refinement and voice paths emit the same `prompt_submitted`, `prompt_structured`, and
`flow_failed` events with sanitized typed fields only. Gate metrics are derived by
`scripts/derive_phase1_metrics.py` from the local JSONL sink plus a separate sanitized
user-study hook (`/metrics/user-study`) that records only completion, quality score,
voice-intent correctness, and refine-cycle counts. The hook must never carry raw prompts,
transcripts, audio, provider exceptions, API keys, or participant PII.

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
| `asset_not_found` | unknown `asset_id` / `job_id` | 404 |
| `asset_invalid` | importer rejects the asset (#7 validation) | 422 |

Error responses carry **only** the typed `error_code` + a safe human message — never the
raw Claude/Meshy exception text (it can leak keys/paths; see §7). Async failures surface
as `status: "failed"` + `error_code` on `GET /jobs/{job_id}`. Errors emit `flow_failed`
with the `error_code`.

---

## 7. Security invariants (hold for every M1 PR)

1. `ANTHROPIC_API_KEY` / `MESHY_API_KEY` are read from env, **server-side only** — never
   in the client, never committed, never logged.
2. No secret value appears in any committed file (`.env.example` carries names only).
3. Meshy generation has a per-run spend guard.
4. `GET /assets/{asset_id}` validates `asset_id` against the UUID format / a known
   manifest and serves **only** from the `assets/generated/` cache — it never interpolates
   client input into a filesystem path (no path traversal / arbitrary file read).
5. Error bodies and logs are sanitized: typed code + safe message only; never echo raw
   provider exception strings.
6. **Persistence (#19/#20):** the server cache is **ephemeral** — saved/exported worlds
   must persist the asset binary + manifest themselves; regeneration from `source_url` is
   not guaranteed (it may have expired).
7. #5/#6 are **security-shape** PRs → merge gate is **≥ 2 NON-xAI lineages** APPROVE.

---

*LOCKED for M1. Any change lands here first, then in the affected issues. Cross-reviewed
by agy (Google) + codex (OpenAI) on 2026-05-30; their CRITICAL/IMPORTANT findings —
prompt-provenance, async job model, single client fetch path, import/placement semantics,
asset-serving path safety — are incorporated.*
