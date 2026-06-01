# E2E Test Strategy and Secrets Policy

This document defines the deploy-readiness test boundary for Phase 1 without spending
external API credits. It conforms to the locked architecture contracts, especially
`docs/architecture/0002-m1-data-contracts.md` sections 2, 5, and 7.

## Test Strategy

Phase-1 CI is mock-only. Pull requests must validate the contract shape and failure
handling without calling Claude, Meshy, speech-to-text providers, Firebase, GCP, or any
other paid external service.

The default CI boundary is:

- AI service contract tests use fake Claude, Meshy, and STT clients.
- Unity-facing tests remain source/fixture validators unless a later dedicated runtime
  harness is approved.
- Golden-prompt acceptance is a versioned input corpus plus a mock `/spec` harness. The
  corpus provides stable `prompt_id` values for telemetry and Gate 1->2 scoring, but the
  real-provider viability run is separate and explicitly budgeted.
- Provider smoke tests with real keys are manual, opt-in, and outside pull-request CI.
  They must use capped accounts, short prompt lists, and recorded evidence rather than
  silently spending during routine validation.

Contract tests check the invariants that decide whether a later real run is meaningful:

- `/spec` returns a schema-valid 0002 section 2 `Spec` with no raw provider output.
- `/generate` and `/create` use the async job model and never expose provider keys or
  provider asset URLs to the client.
- Telemetry events use only the locked 0002 section 5 event names and sanitized typed
  fields.
- Save/load/export preserve 0003 world-document invariants, including path confinement
  and checksum verification.
- Refinement and voice routes conform to 0004 while sharing the typed error and telemetry
  rules from 0002.

## Secrets Policy

Secrets are server-side only. `ANTHROPIC_API_KEY`, `MESHY_API_KEY`, STT provider keys,
GCP credentials, Firebase credentials, database URLs, and storage credentials must never
be committed, sent to the Unity client, included in telemetry, or echoed in error bodies.

Allowed committed files may contain names only. `.env.example` documents variable names
with empty values and safe comments; it must not contain real, dummy, or copied provider
credential values. Local `.env` files and credential material remain gitignored and must
not be read, copied, reviewed, or committed.

Rotation and scope rules:

- Scope keys to the least privilege needed for the Phase-1 service.
- Rotate a key immediately after suspected exposure, accidental logging, contractor
  handoff, or provider dashboard access change.
- Prefer separate development, CI, and production keys when real-provider tests are
  approved.
- Do not reuse personal provider keys for shared CI or deployment.
- Keep the Meshy spend guard enabled for any environment that can call generation.

Scanning rules:

- Every pull request runs the `Secret Scan` workflow using Gitleaks.
- The scan must fail on committed secret values.
- Names-only templates such as `.env.example` must pass because they contain empty values.
- When the scanner reports a true secret, remove the value from git history or rotate the
  key before merge. Do not suppress true positives in project config.

## Release Readiness

A release candidate is ready for manual real-provider evaluation only when:

- Mock-only CI is green, including secret scanning.
- The golden-prompt suite passes through the mock `/spec` harness.
- No secret values appear in committed files, logs, telemetry fixtures, or PR comments.
- The real-provider run has an explicit owner, budget, key scope, and rollback plan.
