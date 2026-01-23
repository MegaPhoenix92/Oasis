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
| Game Engine | Unreal Engine 5.5 |
| Cloud Infrastructure | Google Cloud Platform (GCP) |
| AI Integration | Claude AI with MCP (Model Context Protocol) |
| Networking | Dedicated servers (native UE5) |

## Status

- [x] Project initialization
- [ ] Architecture documentation
- [ ] MVP scope definition
- [ ] Cost modeling
- [ ] Proof of concept development

## Key Decisions

1. **Native Client First** - Building a native UE5 client rather than browser-based
2. **No Pixel Streaming Initially** - Direct rendering on client devices for best experience
3. **AI-Native Creation** - AI companions as first-class citizens in world building

## Project Structure

```
Oasis/
├── docs/           # Documentation
│   ├── architecture/   # System architecture
│   ├── scope/          # MVP scope documents
│   └── costs/          # Cost models
├── src/            # Source code
│   ├── client/         # UE5 client
│   ├── server/         # Dedicated server
│   └── ai/             # AI integration
├── assets/         # 3D assets, textures
└── infrastructure/ # IaC, deployment configs
```

## License

Proprietary - TROZLAN

---

*Part of the TROZLAN ecosystem*
