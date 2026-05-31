# M4 Playable Demo Runbook

Issue #23 defines the Phase-1 M4 demo as a stable 10-minute walkthrough of the full
Oasis creation loop. This runbook is the operator script for a local Unity PoC run and
the source of truth for the mock validator in `scripts/validate_m4_demo.py`.

## Demo Goal

Show one uninterrupted create -> refine -> voice -> explore -> capture -> save loop on a
PC desktop build or Unity Editor session. The demo is technical validation, not a
market launch. It must not require accounts, multiplayer, VR, mobile, cloud sync, or
marketplace features.

## 10-Minute Run Of Show

| Time | Segment | Operator action | Evidence |
| --- | --- | --- | --- |
| 0:00-0:45 | Reset | Start the backend, open `OasisPoC`, verify the scene, grid, lighting, first-person explorer, and creator UI are visible. | Clean scene; no error state. |
| 0:45-2:00 | Create | Submit `a medieval wooden treasure chest with iron bands`. Wait for `/create -> /jobs -> /assets` to complete and preview the generated asset. | Telemetry includes `prompt_submitted`, `prompt_structured`, `generation_submitted`, `generation_ready`, and `asset_downloaded`. |
| 2:00-3:00 | Place | Move the placement marker to a clear ground point and place the asset. | Telemetry includes `asset_imported` and `object_placed`; object has physics/collision. |
| 3:00-4:15 | Refine | Select the placed object and type `make it larger and rotate it slightly`. Apply the transform refine, then run a respec refine `add carved gold trim` if provider time allows. | Undo/redo remains available; refine preserves the selected instance. |
| 4:15-5:15 | Voice | Press Voice, say or paste transcript `add a matching wooden table`, then submit through the same typed router. | Voice transcript uses `/voice/transcribe`; no audio or transcript is persisted to telemetry. |
| 5:15-6:30 | Explore | Enter first-person mode and walk around the placed objects. Show collision, lighting, and day/night control. | Explorer camera moves without corrupting saved transforms. |
| 6:30-7:30 | Capture | Take one screenshot and one short clip frame sequence. | Capture output stays inside the configured local capture directory. |
| 7:30-8:45 | Save | Save the world locally, then load it back. | World document reloads with object transforms and local GLB/manifest assets. |
| 8:45-9:30 | Metrics | Run the Phase-1 metric derivation against the local telemetry JSONL and sanitized study hook. | Generation latency, completion, voice intent, refine cycles, quality, and frame-time evidence are visible. |
| 9:30-10:00 | Close | State the remaining Gate 1->2 decision evidence and stop. Do not start Gate 1->2 build work. | Demo evidence is ready for #25. |

## Fallback Scenarios

Fallback A: provider timeout or Meshy outage

- Use the mock validator evidence from `scripts/validate_m4_demo.py` to show the locked
  `/create -> /jobs -> /assets` path without live provider calls.
- In Unity, load the last locally saved world rather than waiting on a live generation.
- Call out the typed `timeout` or `provider_error` in telemetry; do not paste provider
  exception text into logs or the demo notes.

Fallback B: voice device or STT unavailable

- Paste the intended transcript into the text field and submit it through the same router.
- Keep the voice segment in the script by showing `/voice/transcribe` mock evidence.
- Do not store raw audio; STT temp files must be deleted immediately.

Fallback C: import rejects an asset

- Keep the failed object skipped, show the typed `asset_invalid` or checksum failure,
  then continue with the already placed object.
- Do not bypass manifest validation, checksum verification, or path confinement.

Fallback D: frame budget drops below 60 FPS

- Keep the scene running and record the `unity-frame-budget` JSONL samples.
- Reduce active generation/capture overlap and continue the flow; report the worst frame
  time as manual profiler evidence for Gate 1->2.

Fallback E: save/load failure

- Export the screenshot and short clip as proof of the current scene, then retry save.
- If reload still fails, preserve the typed persistence error and do not hand-edit the
  world document during the demo.

## Operator Checklist

- Backend is local and uses test/mocked providers unless live keys are intentionally
  configured outside the repo.
- `OASIS_TELEMETRY_JSONL` points to a local JSONL path.
- Unity scene `OasisPoC` opens with creator UI, placement marker, first-person explorer,
  capture service, and persistence service wired.
- Demo uses only Phase-1 scope: text/voice creation, refinement, exploration, capture,
  local save/load, and metrics.
- No secrets, raw provider exceptions, raw audio, raw transcripts, or PII are copied into
  telemetry, screenshots, notes, commits, or PR comments.
