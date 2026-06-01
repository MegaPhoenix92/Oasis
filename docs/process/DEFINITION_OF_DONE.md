# Definition of Done

Use this checklist for pull requests and issue closure. A change is done when it is scoped, verified, and safe to merge into the public repository.

## Required

- The pull request links the issue it resolves.
- The change stays within the linked issue scope.
- Relevant roadmap, architecture, scope, cost, or testing docs were checked.
- Any changed behavior is reflected in the appropriate docs.
- Required tests, validators, or documented manual checks pass.
- Provider-dependent or external-service checks use mock-only or offline-safe validation unless the linked issue explicitly authorizes live service use.
- CI is green before merge.
- No secret values, credentials, tokens, private keys, or local environment values are included in the diff.
- Risk and rollback notes are included in the pull request.

## Code Changes

- Add or update focused tests for behavior that can regress.
- Preserve public contracts for schemas, telemetry, persistence, and security unless the issue explicitly changes the contract and the docs are updated first.
- Avoid unrelated refactors.

## Documentation and Process Changes

- Do not introduce new assumptions as facts.
- Label forward-looking numbers, timelines, and targets as estimates.
- Keep public templates and docs generic; do not include private operating details.
- Run the same repository validators that reasonably apply to the changed files.

## UI, Runtime, or Performance Changes

- Include screenshots, videos, profiler output, runbook notes, or other evidence when visual or runtime behavior changes.
- If a runtime test is not available in CI, document the manual evidence and why CI
  coverage is limited.

## Issue Closure

- Confirm the PR body includes the correct `Closes #...` reference.
- After merge, verify the linked issue closed.
- If automatic closure did not happen, close the issue manually with a short evidence note.
