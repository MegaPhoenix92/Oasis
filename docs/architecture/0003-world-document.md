# World Document & Operation Model

**Document:** 0003
**Date:** 2026-05-31
**Status:** Accepted — **LOCKED** for the Batch-2 build (#19 save/load, #20 export, #21 undo/redo)
**Builds on:** [0002 — M1 Data Contracts](0002-m1-data-contracts.md) (the `AssetManifest`), [ADR-0001](adr/0001-engine.md) (Unity)

---

## Purpose

The single locked representation of a **saved world** and the **operations** that mutate
it. It exists so #19 (save/load), #20 (export), and #21 (undo/redo) share one scene format
and one operation model instead of each inventing its own — otherwise export breaks against
save's serialization and undo can't replay. **Do not diverge without updating this doc
first.** If a field looks wrong while building, STOP and flag it.

---

## 1. World Document schema (what #19 saves / loads)

A world is a list of **placed object instances** plus scene metadata. It references assets
by `asset_id` (from the 0002 `AssetManifest`) — it does **not** inline the geometry.

```json
{
  "schema_version": "1.0",
  "world_id": "uuid-v4",
  "name": "My First World",
  "created_at": "2026-05-31T00:00:00Z",
  "updated_at": "2026-05-31T00:00:00Z",
  "scene_settings": { "time_of_day": 0.5 },
  "objects": [
    {
      "instance_id": "uuid-v4",
      "asset_id": "uuid-v4",
      "transform": {
        "position": { "x": 0.0, "y": 0.0, "z": 0.0 },
        "rotation": { "x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0 },
        "scale":    { "x": 1.0, "y": 1.0, "z": 1.0 }
      },
      "created_at": "2026-05-31T00:00:00Z"
    }
  ]
}
```

Rules:
- `instance_id` identifies a **placement** (one asset may be placed many times); `asset_id`
  references the 0002 manifest/asset that supplies the geometry. `instance_id` MUST be
  **unique within a world** — validated on load; duplicates are a typed error.
- **Transform is canonical Unity space**: position/scale in **meters**, rotation as a
  **quaternion** `{x,y,z,w}` (unambiguous, Unity-native — no euler ambiguity). Scale is the
  *additional* transform on top of 0002's import normalization (default `1,1,1`).
- **The transform is the canonical _authored_ placement and is value-stable.** It changes
  **only** via the op-model `move` (§2); runtime simulation/physics MUST NOT mutate it.
  Placed assets may carry **colliders** (player interaction) and are deterministically
  ground-settled at placement (0002 §4 bottom-center pivot + ground-snap), but are
  **kinematic w.r.t. their authored transform thereafter** — so save persists the authored
  value and **`save → load → save` is idempotent**. (Dynamic physics on placed assets, if
  ever needed, is an explicit opt-in that updates this doc first.)
- `scene_settings` is an open, additive object — `time_of_day` (0..1) is the only key now;
  #17's day/night writes here later. Unknown keys are preserved on load, never dropped.
- `schema_version` is required; bump it (and this doc) on any breaking change.

---

## 2. Operation model (what #21 undo/redo replays)

Creator actions are **invertible operations** applied to the `objects` list. The history is
two stacks (undo / redo). Each operation carries everything needed to invert it with no
external lookup.

| Operation | Payload | Inverse |
|-----------|---------|---------|
| `place`  | `{snapshot: <full object entry>}` | `delete(instance_id)` |
| `move`   | `{instance_id, from: transform, to: transform}` | `move(instance_id, to→from)` |
| `delete` | `{snapshot: <full object entry>}` | `place(snapshot)` |

Rules:
- **Both `place` and `delete` snapshot the *entire* object entry** (incl. `instance_id`,
  `asset_id`, `transform`, `created_at`) so redo/undo restore it **byte-for-byte** — no
  regenerated timestamps, no dropped fields. `move` MUST capture the full prior transform
  (`from`), not a delta.
- A new operation clears the redo stack. Undo/redo never call generation or touch assets —
  they only re-apply transforms/placements already in the document.
- Operations mutate the in-memory world; persisting is #19's concern (save the resulting
  World Document, not the op log — the op log is session-scoped unless a later issue says
  otherwise).
- **Scope:** the op model covers `objects` mutations only. `scene_settings` changes (e.g.
  `time_of_day`) are **not** tracked in undo/redo — deferred to #17 (day/night).

---

## 3. Save / load semantics (#19)

- **A saved world is self-contained and client-local** (per 0002 §7: the server's
  `assets/generated/` cache is **ephemeral**, so a save must not depend on it). Each world
  is a **per-world directory on the client filesystem** (not the server cache):
  ```
  <client worlds>/<world_id>/
  ├── world.json                # the §1 World Document
  ├── manifests/<asset_id>.json # the 0002 AssetManifest for each referenced asset
  └── assets/<asset_id>.glb     # the GLB binary for each referenced asset
  ```
  On save, the client obtains each referenced GLB via the **0002 client contract**
  (`GET /assets/{asset_id}` — the manifest `fetch_path`), **never** by reading the server's
  `local_path`, and writes it + the manifest into the dir.
- **Save is all-or-nothing (LOCKED):** if any referenced GLB cannot be resolved at save
  time (e.g. evicted from the ephemeral cache before it's fetched), **fail loudly — abort
  the save and surface the error.** Never write a partially-populated world dir (that would
  silently truncate the world on the next load).
- **Path safety (LOCKED):** resolution is `world_id`/`asset_id` (UUID-validated) → the
  per-world dir only — **never** interpolate a user-supplied name/path into the filesystem
  (no traversal, no reads outside `<worlds>/<world_id>/`).
- **Load = validate + reconstruct:** parse `world.json` → validate against §1 (incl. unique
  `instance_id`) → for each object, **verify its GLB against the manifest `checksum_sha256`**,
  then import from the per-world `assets/` dir (not the live cache) and apply the transform.
- **Missing/corrupt asset on load:** skip that object gracefully (log it, optional
  placeholder) — **never crash the load**. Mirrors 0002's import rules.
- Schema-invalid `world.json` → typed error, not a partial/garbage world.

---

## 4. Export bundle (#20)

Export is simply a **portable archive of the §3 per-world directory** — same layout, zipped:

```
<filename>.oasisworld   (zip of <worlds>/<world_id>/)
├── world.json
├── manifests/<asset_id>.json
└── assets/<asset_id>.glb
```

Rules:
- **Bundle filename** is derived from a **sanitized** display name (or just `<world_id>`) —
  **never** use the raw `name` as a filesystem path (traversal / invalid-char safety).
- **Binary resolution is bundle-relative (LOCKED):** on import, each object's GLB is loaded
  from the bundle's `assets/<asset_id>.glb` keyed by `asset_id`. The manifest's 0002
  `local_path`/`fetch_path` are backend-context and **ignored** when importing a bundle —
  never resolve a bundle asset against the server cache.
- Export gathers **every** `asset_id` referenced in `objects`; if one can't be resolved,
  fail loudly (don't ship a broken bundle).
- **On import, verify each GLB against its manifest `checksum_sha256`** before use; mismatch
  → skip that object gracefully (§3 rules), never crash.
- The bundle re-imports on a clean machine with **no** server/cache and **no** `source_url`
  dependency. Round-trip (export → import) reproduces the same world.

---

## 5. Invariants (hold for every Batch-2 PR)

1. Path resolution is UUID→per-world-dir only; never user-string→path (no traversal, no
   out-of-dir reads). Bundle filenames are sanitized (or `world_id`), never raw `name`.
2. Transforms are meters + quaternion in Unity space; no euler, no ambiguous units.
3. `place` and `delete` carry full object snapshots; `move` carries the full prior
   transform — so undo **and** redo are byte-exact and lookup-free.
4. `instance_id` is unique within a world (validated on load).
5. Saved worlds **and** export bundles are self-contained (manifest + GLB travel); bundle
   assets resolve **bundle-relative by `asset_id`**, never against the ephemeral cache or
   `source_url`; import verifies `checksum_sha256`.
6. Load and bundle-import degrade gracefully on a missing/corrupt asset — never crash.
7. Tests are mock-only, no network; CI stays green. Never read/commit
   CLAUDE.md/AGENT*.md/GEMINI.md/.env/secrets (public repo).
8. The saved `transform` is the **authored placement**, mutated **only** by the op-model
   `move`; runtime physics never drifts it (placed assets are **kinematic** w.r.t. their
   authored transform post-placement). **`save → load → save` is idempotent.** Dynamic
   physics on placed assets, if ever needed, is an explicit opt-in that updates this doc.

---

*LOCKED for Batch 2. Any change lands here first, then in #19/#20/#21. Cross-reviewed
2026-05-31 by codex (OpenAI) + an independent code-reviewer (agy and kimi were both down
on retry); incorporated findings — full `place`/`delete` snapshots for byte-exact redo,
unique `instance_id`, self-contained client-local save (GLB fetched via the 0002 endpoint,
not the server cache), all-or-nothing save, load-time checksum, bundle-relative resolution
+ sanitized filenames + checksum verify.*

*Amended 2026-05-31 (Batch 3a seam-check, advisor-vetted):* **ADDED** the transform
value-stability invariant (§1 + §5.8). The original locked §1 specified only the transform
*representation* (meters + quaternion); Batch 3a's placed-asset physics surfaced that runtime
gravity could drift the saved transform, making `save → load → save` non-idempotent — a real
persisted-state corruption. The guarantee is now explicit; fix-forward tracked in #91.
