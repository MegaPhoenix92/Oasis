# OASIS Virtual World Initiative: MVP Scope Document

**Document Version:** 1.0
**Date:** 2026-01-23
**Classification:** Strategic R&D Planning
**Author:** Architecture Advisor

---

## Executive Summary

This document presents three scope tiers for the OASIS virtual world initiative, each representing a distinct risk/reward profile and resource commitment. The tiers are designed as sequential gates - each tier validates assumptions necessary for the next.

**Key Recommendation:** Start with Tier 1 to prove TROZLAN's AI-native differentiator before expanding scope. Attempting Tier 2 or 3 without Tier 1 validation significantly increases failure risk.

---

## Tier 1: Focused MVP (Prove the Tech)

### Strategic Objective
Validate that TROZLAN's AI-assisted creation tools provide a meaningful differentiation in virtual world building. This tier is purely technical validation - not market validation.

### Platform Target
**PC Desktop (Windows/macOS)** - Single platform focus

**Rationale for PC-first:**
- Lowest deployment friction (no app store approvals)
- Highest GPU availability for AI inference
- Fastest iteration cycles
- VR support adds complexity without proving core hypothesis

### Core Loop
```
User describes world element (text/voice)
    ↓
AI generates 3D asset/terrain/structure
    ↓
User refines through natural language
    ↓
User places and arranges in scene
    ↓
User explores creation in first-person
```

### Timeline: 16 Weeks (4 Months)

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Foundation | Weeks 1-4 | Engine selection, AI pipeline prototype, basic renderer |
| Core AI | Weeks 5-10 | Text-to-3D, voice input, asset generation pipeline |
| Integration | Weeks 11-14 | Scene composition, first-person navigation, persistence |
| Polish | Weeks 15-16 | Performance optimization, demo preparation |

### Team Composition: 4-5 People

| Role | Count | Responsibility |
|------|-------|----------------|
| Technical Lead | 1 | Architecture, AI integration, engine work |
| 3D/Graphics Engineer | 1 | Rendering, asset pipeline, optimization |
| AI/ML Engineer | 1 | Generative models, inference optimization |
| Full-stack Developer | 1 | UI, persistence, tooling |
| Designer (part-time) | 0.5 | UX, demo scenarios, user testing |

### Features IN Scope

**AI Creation Tools:**
- Text-to-terrain generation (natural landscapes, basic structures)
- Voice-to-object creation (furniture, props, simple buildings)
- Iterative refinement ("make it bigger", "add windows", "change to wood")
- Style transfer ("make it look medieval", "cyberpunk aesthetic")

**World Interaction:**
- First-person exploration of created worlds
- Basic physics (collision, gravity)
- Day/night cycle for atmosphere
- Screenshot/video capture of creations

**Persistence:**
- Local save/load of world state
- Export created assets (standard 3D formats)
- Basic undo/redo for creation actions

### Features OUT of Scope

- Multiplayer/networking (no social features)
- VR support (adds 3+ months complexity)
- Mobile platforms (performance constraints)
- User accounts/cloud sync (infrastructure overhead)
- Marketplace/commerce (premature)
- AI NPCs or agents (scope creep risk)
- Real-time collaboration (networking complexity)
- Cross-platform saves (single platform only)

### Technical Milestones

| Milestone | Week | Criteria |
|-----------|------|----------|
| M1: First AI-generated asset | 4 | Text prompt produces placeable 3D object |
| M2: Scene composition | 8 | Multiple AI assets in coherent scene |
| M3: Natural language refinement | 10 | Modify existing objects via voice/text |
| M4: Playable demo | 14 | 10-minute demo showcasing full loop |
| M5: Performance target | 16 | 60 FPS on mid-range GPU with active generation |

### Success Metrics (Quantifiable)

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Generation latency | < 30 seconds for simple objects | Automated timing logs |
| Asset quality score | 7/10 user rating average | 10-person user study |
| Creation flow completion | 80% of test users complete basic scene | User testing sessions |
| Voice recognition accuracy | 90% intent recognition | Structured command tests |
| Iteration cycles | < 3 refinements to acceptable result | User session tracking |

### Go/No-Go Decision Criteria

**GO to Tier 2 if:**
- All success metrics achieved
- User testers express genuine interest (qualitative)
- AI generation quality competitive with existing tools (Blockade Labs, Luma)
- Team confidence in scaling architecture

**NO-GO if:**
- Generation latency exceeds 2 minutes for simple objects
- Asset quality consistently below 5/10 rating
- Users prefer manual tools over AI assistance
- Core tech proves infeasible on consumer hardware

### Tier 1 Specific Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| AI model quality insufficient | Medium | High | Evaluate multiple foundation models early; plan fallback to hybrid approach |
| GPU requirements too high | Medium | Medium | Cloud inference as fallback; optimize for consumer GPUs |
| Voice recognition unreliable | Low | Medium | Text input as primary, voice as enhancement |
| Engine limitations | Low | High | Proof-of-concept before committing to engine |

### Budget Estimate (USD, 4 months)

| Category | Monthly | Total |
|----------|---------|-------|
| Personnel (5 x avg $15K) | $75,000 | $300,000 |
| Cloud compute (AI inference) | $5,000 | $20,000 |
| Software licenses | $2,000 | $8,000 |
| Hardware (dev machines) | - | $15,000 |
| Contingency (15%) | - | $51,450 |
| **Total** | - | **$394,450** |

---

## Tier 2: Expanded Alpha (Validate Market)

### Strategic Objective
Validate market demand for AI-native virtual worlds. This tier proves people will use the product socially and return regularly.

### Platform Targets
- **Primary:** PC Desktop (Windows/macOS)
- **Secondary:** Meta Quest (standalone VR)

### Timeline: 12 Months
### Team: 10-12 People
### Budget: ~$2.6M

### Key Features
- User accounts with persistent identity
- Real-time multiplayer (8-16 concurrent users per world)
- Spatial voice chat
- Collaborative building
- Public world gallery
- Quest VR port

### Success Metrics
- D7 retention: 30%+
- D30 retention: 15%+
- Average session length: 20+ minutes
- Social sessions (2+ users): 40%+ of sessions

---

## Tier 3: Full Vision (The "OASIS")

### Strategic Objective
Build a persistent, interconnected virtual world platform.

### Timeline: 30 Months
### Team: 25-35 People
### Budget: ~$45M

### Features
- All platforms (PC, VR, Quest, mobile via streaming)
- Creator economy with marketplace
- Advanced AI NPCs
- Live events infrastructure
- Enterprise/education features

### Success Metrics (30-Month)
- 2M+ Monthly Active Users
- 400K+ Daily Active Users
- $10M+ ARR

---

## Tier Comparison Summary

| Attribute | Tier 1 | Tier 2 | Tier 3 |
|-----------|--------|--------|--------|
| **Objective** | Prove tech | Validate market | Build platform |
| **Timeline** | 4 months | 12 months | 30 months |
| **Team size** | 4-5 | 10-12 | 25-35 |
| **Budget** | ~$400K | ~$2.6M | ~$45M |
| **Platforms** | PC only | PC + Quest | All major |
| **Users** | 10-20 testers | 500-1K alpha | 2M+ MAU |
| **Success probability** | 70% | 45% | 20% |

---

## Recommendation

**Start Tier 1 immediately with existing resources.**

Tier 1 requires ~$400K over 4 months - manageable for R&D exploration. The output validates whether TROZLAN's AI differentiation is real and valuable.

---

*Document Control: Created 2026-01-23 | Review cycle: Monthly*
