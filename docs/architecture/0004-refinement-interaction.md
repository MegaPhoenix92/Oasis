# Refinement & Interaction Contract

**Document:** 0004
**Date:** 2026-05-31
**Status:** Accepted — **LOCKED** for the Batch-3b build (#15 iterative NL refinement + style-transfer, #16 voice input)
**Builds on:** [0002 — M1 Data Contracts](0002-m1-data-contracts.md) (the `Spec`, the async `/create→/jobs→/assets` pipeline, the spend guard), [0003 — World Document & Operation Model](0003-world-document.md) (the undo/redo op-model), [ADR-0001](adr/0001-engine.md) (Unity)

---

## Purpose

The single locked representation of **refining an existing object** ("make it bigger", "add
windows", "make it medieval") and of the **voice input** that drives the same pipeline. It
exists so #15 (refinement/style-transfer) and #16 (voice) plug into the **already-locked**
0002 Spec pipeline and 0003 op-model **without** each inventing its own refine semantics —
otherwise undo can't reverse a refine, or a refine silently regenerates on undo and runs up
Meshy cost. **Do not diverge without updating this doc first.** If a rule looks wrong while
building, STOP and flag it.

This contract changes **no** existing schema. It *adds* one endpoint, one op-model
operation, and one input adapter, all conforming to 0002/0003.

---

## 1. What a refinement is (#15)

A refinement takes **one selected, already-placed object instance** (an `objects[]` entry
from the 0003 World Document) plus a **follow-up natural-language directive**, and produces a
**modified instance**. There are exactly **two kinds**, and the AI service decides which:

| Kind | Directive examples | What changes | Cost | Op-model |
|------|--------------------|--------------|------|----------|
| **transform** | "bigger", "smaller", "taller", "rotate 90°", "move it left" | only the 0003 `transform` (position/rotation/scale) | **$0** — no generation | reuses 0003 **`move`** |
| **respec** | "add windows", "make it medieval", "change wood to stone", "add a chimney" | geometry/identity → a **new `Spec`** → a **new asset** (new `asset_id`) | **1 Meshy generation** | new 0004 **`refine`** op (§3) |

Rules:
- The **same `instance_id` is preserved** across both kinds — a refine mutates an existing
  placement, it never creates/destroys one. (delete-old + place-new is **wrong**: it would
  change `instance_id` and cost two undo steps for one user action.)
- A **respec** refine produces a **new `asset_id`**; the prior asset is *not* mutated in
  place (assets are immutable once generated — they may be referenced by other instances or
  by the undo stack). A **transform** refine keeps the **same `asset_id`**.
- Classification (transform vs respec) is the AI service's job, returned explicitly (§2) —
  the client never guesses. When ambiguous, default to **respec** (correctness over cost is
  acceptable for the PoC; the spend guard §6 still bounds it).

---

## 2. The refine endpoint (0002 extension, #15)

One new backend endpoint, conforming to 0002 (Python/FastAPI service in `src/ai`, keys
server-side). **`/refine` is SYNCHRONOUS** — it classifies the directive and returns the
`RefineResult` (a new `Spec` *or* a transform delta) **in the response body**. It does **not**
submit a Meshy job and **never** returns a `job_id`. Only the *subsequent* `/generate` (the
respec path, below) is the async job from 0002.

| Method / path | Input | Output |
|---------------|-------|--------|
| `POST /refine` | `{ "prior_spec": <0002 §2 Spec>, "directive": "<text>" }` | `RefineResult` (synchronous) |

`prior_spec` is the **selected instance's `Spec`**, resolved client-side from the instance's
`asset_id` → its 0002 `AssetManifest.spec` (0002 §4) — no new lookup endpoint; the manifest
already travels with the world.

```json
{
  "kind": "transform" | "respec",
  "transform_delta": {            // present iff kind == "transform"
    "scale_factor":   { "x": 1.5, "y": 1.5, "z": 1.5 },
    "rotation_delta": { "x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0 },
    "translate":      { "x": 0.0, "y": 0.0, "z": 0.0 }
  },
  "spec": { "...": "a new 0002 §2 Spec" },   // present iff kind == "respec"
  "rationale": "interpreted 'add windows' as a geometry change"
}
```

Rules:
- **Exactly one** of `transform_delta` / `spec` is present, matching `kind` — a discriminated
  result; the client switches on `kind` and never guesses.
- When `kind == "respec"`, `spec` is a **full, valid 0002 §2 `Spec`** (`extra=forbid`,
  `dimensions > 0`, non-empty `meshy_prompt`, `schema_version` "1.0"), **derived from**
  `prior_spec` + `directive` (carries forward `object_type`, merges `materials`/`details`,
  updates `style`). Provenance fields are set deterministically:
  - `source_prompt` = the **composed lineage** `"<prior_spec.source_prompt> → <directive>"`.
    This **overrides** 0002 §2's "raw user input verbatim" wording **for refine-derived
    specs** (provenance lineage over verbatim — a refine has no single raw prompt).
  - `normalized_prompt` = the **0002 §2 normalization of that composed `source_prompt`**
    (lowercased, trimmed, whitespace-collapsed), so 0002's invariant
    `normalized_prompt == normalize(source_prompt)` still holds.
- **Generation is client-orchestrated, single-path.** For a respec, the **client** then
  drives the **existing** `POST /generate → /jobs/{id} → /assets/{id}` flow with the new
  `Spec`. `/refine` itself never generates. **There is no `/refine/create` convenience
  endpoint** — it is explicitly out of scope, so two builders can't fork into two generation
  paths.
- When `kind == "transform"`, `transform_delta` composes over the instance's **current**
  transform (scale **multiplies**, rotation **composes** as quaternion, translate **adds**) —
  meters + quaternion, **never euler/degrees** in the payload. **No Meshy call** happens.
- `/refine` reuses 0002's **error model** (§6) and **sanitized errors** (§7) verbatim — a bad
  directive → `invalid_prompt` (400); un-parseable model output → `model_parse_error` (502);
  never echo raw provider text.

---

## 3. Refine ↔ op-model — the load-bearing seam (0003 §2 extension, #15 + #21)

A **respec** refine swaps an instance's `asset_id` (and possibly `transform`). To stay
**byte-exact undoable** (0003's core invariant) it adds **one** operation to the 0003 model:

| Operation | Payload | Inverse |
|-----------|---------|---------|
| `refine` | `{before: <full object entry>, after: <full object entry>}` | swap `after`→`before` |

Rules (these are the reason this doc exists):
- **`refine` snapshots the ENTIRE before AND after object entry** (`instance_id` — identical
  in both —, `asset_id`, `transform`, `created_at`). Undo restores `before`, redo restores
  `after`, **byte-for-byte** — same as 0003 `place`/`delete`. `move` (transform refine) is
  unchanged: it already carries full `from`/`to` transforms.
- **Undo/redo of a refine NEVER calls generation** (0003 §2 holds): both the `before` and
  `after` assets already exist as GLB bytes on the client. The owner of those bytes is a
  **client-side in-session asset store** — an in-memory / client-local-temp store owned by
  the creator session, **distinct from** (a) the server's ephemeral `assets/generated/` cache
  (freely evictable per 0002 §7) and (b) the saved per-world dir (0003 §3). When a respec
  replaces asset **A** with **B** on an instance, the client already holds **A**'s bytes in
  this in-session store (from when A was first placed/loaded) and fetches **B** via
  `/assets/{B}` (0002). The `before` snapshot's asset **A is pinned in the in-session store**
  while any history-stack op references it, so **undo restores A from the in-session store
  with no `/generate` call**. The server cache is **never** relied on for undo. Eviction from
  the in-session store is allowed **only** when an asset is referenced by neither the current
  document nor either history stack.
- **The respec commit is ATOMIC.** Importing asset B, swapping the instance's
  `asset_id`/`transform` in the document, and pushing the `refine` op happen as **one
  transaction**. The op is pushed **only after** B is `ready` and the instance updated. If
  **any** step fails (generation failed/cancelled, import error, swap error), the instance is
  restored to `before` and **nothing** is pushed — no half-applied refine, no dangling op, no
  non-undoable state.
- **One in-flight respec per object.** While a respec generation is in flight for an instance,
  further refine directives on it are blocked at the UI (the object shows a "refining" state)
  — no overlapping respecs, no racing commits.
- A new operation clears the redo stack (0003 §2, unchanged) — including after a refine.
- **`scene_settings` is still out of the op model** (0003 §2); refinement only ever mutates
  `objects[]`.

### Interaction with save/load (0003 §3) — no change, one clarification
The history (incl. `refine` ops and their pinned in-session `before` assets) is
**session-scoped and not persisted** (0003 §2). On **save**, only assets referenced by the
**current** World Document persist (0003 §3) — a refined-away `before` asset is *not* saved,
because after the save+reload there is no in-session undo stack that could reach it. This is
consistent with 0003; **no new persistence rule is introduced.** (A future "persistent
history" issue, if ever filed, would update 0003 first.)

---

## 4. Style-transfer (#15)

Style-transfer ("make it medieval", "cartoon style", "weathered") is a **respec** refine
whose directive changes `Spec.style` (and possibly `materials`/`details`/`meshy_prompt`) but
keeps `object_type` and `dimensions`. It takes the **§2 `/refine` → respec** path with **no
special casing** — same new `asset_id`, same `refine` op, same spend accounting. It is called
out here only so builders don't build a *separate* style endpoint: there is **one** refine
path, and style is a `respec` directive.

---

## 5. Voice input (#16)

Voice is an **input adapter**, not a new data path. Speech-to-text (STT) yields a **text
string** that is fed to the **same** pipeline as typed text:

```
mic → STT → text directive ──▶ (no object selected)        → POST /create   (0002)
                             └▶ (an object is selected)     → POST /refine   (0004 §2)
```

Rules:
- **STT runs server-side**, behind the `src/ai` service, with any STT-provider key held
  **server-side only** (0002 §1/§7 — never in the client, never committed, never logged). The
  client sends audio (or a transcript from an on-device recognizer) to the service; the
  service never returns the provider key.
- **One router, shared with typed text.** STT output goes to the **exact same**
  selected-object command router as typed input — there is **no** voice-specific intent
  classifier. Routing is **selection-state only**: if a creator object is **selected** →
  `POST /refine` (the `/refine` service classifies transform vs respec and returns
  `invalid_prompt` if the directive isn't a valid refinement); if **none** is selected →
  `POST /create`. (The 90% intent-recognition target in #16 is an *acceptance metric*, not
  part of this contract.)
- **Voice never bypasses the text pipeline.** STT output is treated **identically** to typed
  text — same `Spec`/`RefineResult` schemas, same validation, same op-model, same spend guard.
  There is no "voice-only" code path that skips a contract.
- **Audio is transient** — never written to the World Document, a saved/exported world,
  durable storage, telemetry, or logs. Any STT temp file is **deleted immediately after
  transcription**. Only the resulting `Spec`/transform (and its asset) persist, exactly as for
  typed input.

---

## 6. Spend control (extends 0002 §3)

- A **respec** refine is a generation → it **counts against the same per-run Meshy spend
  guard** as `/create` (0002 §3 / the `OASIS_MESHY_MAX_GENERATIONS` ceiling). A refine loop
  ("add a window / no, bigger / add a door") cannot exceed the cap.
- A **transform** refine and an **undo/redo of any refine** are **$0** — they make **no**
  Meshy call. (This is *why* §1 routes pure transform directives away from regeneration and §3
  forbids regeneration on undo.)

---

## 7. Invariants (hold for every Batch-3b PR)

1. A refine **preserves `instance_id`**; it never does delete-old + place-new. `respec`
   refine → **new `asset_id`**; `transform` refine → **same `asset_id`**.
2. The AI service **classifies** transform vs respec and returns it explicitly (discriminated
   `RefineResult`, exactly one of `transform_delta`/`spec`); the client never guesses.
   Ambiguous → respec.
3. `respec` refine emits a **full valid 0002 §2 `Spec`** with composed `source_prompt`
   lineage + matching `normalized_prompt`, then drives the **existing**
   `/generate→/jobs→/assets` flow. `/refine` is **synchronous**; generation is **client-
   orchestrated, single-path** — **no `/refine/create`**, no new generation/fetch path.
4. `respec` refine adds the 0003 op `refine{before, after}` carrying **full** object snapshots
   → undo **and** redo are byte-exact. **Undo/redo never regenerate.** `transform` refine
   reuses 0003 `move`.
5. The client pins each `refine` `before` asset (manifest + GLB) in a **client-side in-session
   asset store** — distinct from the server's ephemeral cache **and** the saved per-world dir
   — while reachable on either history stack; undo restores from it with **no** `/generate`;
   eviction only when unreferenced by document **and** both stacks.
6. The respec commit (import B + swap instance + push op) is **atomic**; any failure restores
   `before` and pushes **no** op — no non-undoable state. **One in-flight respec per object.**
7. Voice STT output uses the **same** selection-state router as typed text (no voice-specific
   classifier); STT key **server-side**; **audio never written to world/export/durable
   storage/telemetry/logs** (temp files deleted post-STT); no contract-skipping voice path.
8. Refine generations count against the **same** 0002 spend guard; transform + undo/redo are
   $0.
9. `/refine` reuses 0002's typed, **sanitized** error model — never echo raw provider text.
10. Tests are **mock-only, no network**; CI stays green. Never read/commit
    CLAUDE.md/AGENT*.md/GEMINI.md/.env/secrets (public repo).

---

*LOCKED for Batch 3b. Any change lands here first, then in #15/#16. Cross-reviewed 2026-05-31
by codex (OpenAI) + an independent code-reviewer subagent (Anthropic), both reading the draft;
agy (Google) reviewed against 0002/0003 only (its sandbox lacked the uncommitted draft) and
independently **confirmed** the session-cache CRITICAL — its separate suggestion to persist
undo-stack assets across save/reload was **rejected** as contradicting 0003 §2 (the op log is
session-scoped). Incorporated the CRITICAL/IMPORTANT findings: named the **client-side
in-session asset store** as the `before`-asset owner (was an undefined "session cache" that
collided with 0002's ephemeral server cache — the silent-regeneration trap this doc exists to
prevent); made `/refine` **synchronous** with a single client-orchestrated generation path (no
`/refine/create`); made the respec commit **atomic** (import + swap + push, restore-on-fail);
fixed `source_prompt`/`normalized_prompt` provenance vs 0002 §2; collapsed voice routing to a
**single selection-state router** shared with typed text (no voice classifier); hardened audio
non-persistence (no durable/telemetry/logs, temp deleted).*
