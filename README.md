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
- [ ] Proof of concept development

## Key Decisions

1. **Native Client First** - Building a native Unity client rather than browser-based (engine choice: [ADR-0001](docs/adr/0001-engine.md))
2. **No Pixel Streaming Initially** - Direct rendering on client devices for best experience
3. **AI-Native Creation** - AI companions as first-class citizens in world building

## Project Structure

```
Oasis/
├── docs/           # Documentation
│   ├── ROADMAP.md      # Unified phase roadmap (start here)
│   ├── architecture/   # System architecture
│   ├── scope/          # MVP scope documents
│   └── costs/          # Cost models
├── src/            # Source code
│   ├── client/         # Unity client
│   ├── server/         # Dedicated server
│   └── ai/             # AI integration
├── assets/         # 3D assets, textures
└── infrastructure/ # IaC, deployment configs
```

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/ROADMAP.md](docs/ROADMAP.md) | Unified phase roadmap — naming, gates, cross-links (**start here**) |
| [docs/architecture/ARCHITECTURE_OVERVIEW.md](docs/architecture/ARCHITECTURE_OVERVIEW.md) | Per-phase system architecture & tech decisions |
| [docs/scope/MVP_SCOPE_DOCUMENT.md](docs/scope/MVP_SCOPE_DOCUMENT.md) | Per-phase features, milestones, success metrics, gate criteria |
| [docs/costs/COST_MODEL.md](docs/costs/COST_MODEL.md) | Per-phase infrastructure & team cost estimates |
| [docs/adr/](docs/adr/) | Architecture Decision Records (ADR-0001: engine choice) |
| [docs/issues/EPIC_AND_SUBISSUE_GUIDE.md](docs/issues/EPIC_AND_SUBISSUE_GUIDE.md) | How agents create epics & sub-issues (backlog structure) |

## License

Proprietary - TROZLAN

---

*Part of the TROZLAN ecosystem*
