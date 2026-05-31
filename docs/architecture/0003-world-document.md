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
  references the 0002 manifest/asset that supplies the geometry.
- **Transform is canonical Unity space**: position/scale in **meters**, rotation as a
  **quaternion** `{x,y,z,w}` (unambiguous, Unity-native — no euler ambiguity). Scale is the
  *additional* transform on top of 0002's import normalization (default `1,1,1`).
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
| `place`  | `{instance_id, asset_id, transform}` | `delete(instance_id)` |
| `move`   | `{instance_id, from: transform, to: transform}` | `move(instance_id, to→from)` |
| `delete` | `{instance_id, snapshot: <full object entry>}` | `place(snapshot)` |

Rules:
- `delete` MUST snapshot the **entire** object entry (so undo restores it exactly, incl.
  `created_at`). `move` MUST capture the full prior transform (`from`), not a delta.
- A new operation clears the redo stack. Undo/redo never call generation or touch assets —
  they only re-apply transforms/placements already in the document.
- Operations mutate the in-memory world; persisting is #19's concern (save the resulting
  World Document, not the op log — the op log is session-scoped unless a later issue says
  otherwise).

---

## 3. Save / load semantics (#19)

- **Location:** worlds are saved under a single known directory (e.g.
  `<user data>/oasis/worlds/<world_id>.json`); the cached GLBs stay in
  `assets/generated/` (0002). One canonical worlds dir — not arbitrary paths.
- **Path safety (LOCKED):** load/import resolves `world_id` to that directory only —
  **never** interpolate a user-supplied name/path into the filesystem (no traversal, no
  reads outside the worlds dir). Validate `world_id`/`asset_id` as UUIDs.
- **Load = validate + reconstruct:** parse → validate against §1 → for each object,
  re-import its asset via the 0002 fetch path / cache and apply the transform.
- **Missing/invalid asset on load:** skip that object gracefully (log it, optional
  placeholder) — **never crash the load**. Mirrors 0002's import rules.
- Schema-invalid file → typed error, not a partial/garbage world.

---

## 4. Export bundle (#20)

Export produces a **self-contained, portable** package (per 0002's rule that saved worlds
persist their binaries — the server cache is ephemeral):

```
<world-name>.oasisworld/   (or .zip)
├── world.json             # the §1 World Document
├── manifests/<asset_id>.json   # the 0002 AssetManifest for each referenced asset
└── assets/<asset_id>.glb       # the GLB binary for each referenced asset
```

Rules:
- Export gathers **every** `asset_id` referenced in `objects`, copying its manifest + GLB.
  An export that can't resolve a referenced asset fails loudly (don't ship a broken bundle).
- The bundle must re-import on a clean machine with **no** server/cache dependency and **no**
  reliance on `source_url` (which may have expired).
- Re-importing a bundle is the inverse of export; round-trip (export → import) must
  reproduce the same world.

---

## 5. Invariants (hold for every Batch-2 PR)

1. One canonical worlds directory; all path resolution is UUID→dir, never user-string→path
   (no traversal, no out-of-dir reads).
2. Transforms are meters + quaternion in Unity space; no euler, no ambiguous units.
3. `delete`/`move` carry full snapshots so undo is exact and lookup-free.
4. Load and bundle-import degrade gracefully on a missing asset — never crash the world.
5. Export bundles are self-contained (manifest + GLB travel); no `source_url` dependency.
6. Tests are mock-only, no network; CI stays green. Never read/commit
   CLAUDE.md/AGENT*.md/GEMINI.md/.env/secrets (public repo).

---

*LOCKED for Batch 2. Any change lands here first, then in #19/#20/#21.*
