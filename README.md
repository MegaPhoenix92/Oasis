# Oasis

**AI-Native Virtual World Platform**

## Vision

Oasis is an AI-native virtual world platform inspired by Ready Player One. A persistent, immersive digital universe where AI companions guide creation, exploration, and social experiences.

## Current Phase

**Tier 1 - Proof of Concept (R&D Exploration)**

We are in the initial research and development phase, validating core technical assumptions and establishing the architectural foundation.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Game Engine | Unity (PoC) — see [ADR-0001](docs/adr/0001-engine.md) |
| Cloud Infrastructure | Google Cloud Platform (GCP) |
| AI Integration | Claude AI with MCP (Model Context Protocol) |
| Networking | Dedicated servers (headless Unity) |

## Status

- [x] Project initialization
- [x] Architecture documentation
- [x] MVP scope definition
- [x] Cost modeling
- [x] Phase roadmap
- [x] Repo hygiene: CI gates, secret scanning, LFS policy, PR/issue templates, Definition of Done
- [x] Proof of concept development — M1 prompt-to-object, refinement, voice, exploration, persistence, capture, M4 demo runbook, M5 frame budget
- [x] Phase-1 metrics instrumentation & golden prompt acceptance suite
- [ ] Gate 1→2 evaluation (PoC exit & production-engine decision — issue #25)

## Key Decisions

1. **Native Client First** - Building a native Unity client rather than browser-based (engine choice: [ADR-0001](docs/adr/0001-engine.md))
2. **No Pixel Streaming Initially** - Direct rendering on client devices for best experience
3. **AI-Native Creation** - AI companions as first-class citizens in world building

## Project Structure

```
Oasis/
├── docs/           # Documentation
│   ├── ROADMAP.md      # Unified phase roadmap (start here)
│   ├── adr/            # Architecture Decision Records
│   ├── architecture/   # System architecture & locked data contracts
│   ├── scope/          # MVP scope documents
│   ├── costs/          # Cost models
│   ├── testing/        # E2E strategy, secrets policy, golden prompts
│   ├── process/        # Definition of Done
│   ├── demo/           # M4 playable demo runbook
│   └── issues/         # Epic & sub-issue backlog guide
├── src/            # Source code
│   ├── client/         # Unity client (scene, import, UI, persistence)
│   ├── server/         # Dedicated server
│   └── ai/             # AI service (FastAPI: spec/generate/refine/voice/metrics)
├── tests/          # Offline contract & behavioral tests (pytest, mocked)
├── scripts/        # Validation scripts run locally and in CI
├── assets/         # 3D assets, textures (Git LFS)
└── infrastructure/ # IaC, deployment configs
```

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/ROADMAP.md](docs/ROADMAP.md) | Unified phase roadmap — naming, gates, cross-links (**start here**) |
| [docs/architecture/ARCHITECTURE_OVERVIEW.md](docs/architecture/ARCHITECTURE_OVERVIEW.md) | Per-phase system architecture & tech decisions |
| [docs/architecture/0002-m1-data-contracts.md](docs/architecture/0002-m1-data-contracts.md) | Locked M1 data contracts (spec, manifest, errors, telemetry) |
| [docs/architecture/0003-world-document.md](docs/architecture/0003-world-document.md) | World Document schema: save/load/export/import invariants |
| [docs/architecture/0004-refinement-interaction.md](docs/architecture/0004-refinement-interaction.md) | Refinement & voice interaction contract |
| [docs/scope/MVP_SCOPE_DOCUMENT.md](docs/scope/MVP_SCOPE_DOCUMENT.md) | Per-phase features, milestones, success metrics, gate criteria |
| [docs/costs/COST_MODEL.md](docs/costs/COST_MODEL.md) | Per-phase infrastructure & team cost estimates |
| [docs/adr/](docs/adr/) | Architecture Decision Records (ADR-0001: engine choice) |
| [docs/DEV_SETUP.md](docs/DEV_SETUP.md) | Development environment setup (Unity, Python, Git LFS) |
| [docs/LFS_POLICY.md](docs/LFS_POLICY.md) | Git LFS policy for mesh/texture binaries |
| [docs/testing/e2e-test-strategy-and-secrets-policy.md](docs/testing/e2e-test-strategy-and-secrets-policy.md) | E2E test matrix & secrets rotation/scanning policy |
| [docs/testing/golden-prompts.md](docs/testing/golden-prompts.md) | Canonical golden prompt suite for M1/Gate-1→2 acceptance |
| [docs/process/DEFINITION_OF_DONE.md](docs/process/DEFINITION_OF_DONE.md) | Definition of Done for every PR |
| [docs/demo/M4_PLAYABLE_DEMO.md](docs/demo/M4_PLAYABLE_DEMO.md) | M4 10-minute playable demo runbook |
| [docs/issues/EPIC_AND_SUBISSUE_GUIDE.md](docs/issues/EPIC_AND_SUBISSUE_GUIDE.md) | How agents create epics & sub-issues (backlog structure) |

## License

Proprietary - TROZLAN

---

*Part of the TROZLAN ecosystem*
