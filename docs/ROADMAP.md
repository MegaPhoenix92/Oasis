# OASIS — Phase Roadmap

**Document Version:** 1.0
**Date:** 2026-05-30
**Classification:** Strategic R&D Planning
**Status:** Consolidation doc — cross-links architecture, scope, and cost

---

## Purpose

This is the single source of truth for **how OASIS progresses through its phases**. It does not replace the detailed docs — it unifies their terminology and links each phase to its architecture, scope, and cost detail, plus the gate criteria that govern moving from one phase to the next.

> **All forward-looking figures here are ESTIMATES** carried over from the source docs. Timelines, budgets, and user numbers are planning assumptions, not commitments. Validate against actuals at each gate.

---

## Canonical naming (Rosetta table)

The three planning docs each use different names for the **same three phases**. This roadmap standardizes on **Phase N**; the aliases below are equivalent.

| This roadmap | Scope doc | Cost doc | Codename | README / CLAUDE.md |
|--------------|-----------|----------|----------|--------------------|
| **Phase 1** | Tier 1 | Scenario 1 | PoC | "Tier 1 – Proof of Concept" |
| **Phase 2** | Tier 2 | Scenario 2 | Alpha | — |
| **Phase 3** | Tier 3 | Scenario 3 | Production | — |

When any doc says "Tier 2," "Scenario 2," or "Alpha," it means **Phase 2**.

---

## Phase progression at a glance

| | **Phase 1 — PoC** | **Phase 2 — Alpha** | **Phase 3 — Production** |
|---|---|---|---|
| **Objective** | Prove the tech | Validate the market | Build the platform |
| **Timeline** | 4 months (16 wks) | 12 months | 30 months |
| **Team** | 4–5 | 10–12 | 25–35 |
| **Phase budget (est.)** | ~$400K | ~$2.6M | ~$45M |
| **Infra CCU target** | 10–50 | 100–500 | 1,000+ |
| **Users** | 10–20 testers | 500–1K alpha | 2M+ MAU |
| **Platforms** | PC only | PC + Quest | All major |
| **Success prob. (est.)** | 70% | 45% | 20% |

> **CCU vs Users:** "CCU" (concurrent users) sizes the infrastructure; "Users" counts the audience (testers / alpha cohort / monthly actives). They are different metrics — a Phase 3 with 2M MAU still only needs 1,000+ *concurrent* capacity per the architecture sizing.

Source: `scope/MVP_SCOPE_DOCUMENT.md:204` (tier comparison), `architecture/ARCHITECTURE_OVERVIEW.md:60` (CCU sizing).

---

## Phase 1 — PoC (current phase)

**Goal:** Validate that TROZLAN's AI-assisted creation tools are a meaningful differentiator. Technical validation only — *not* market validation.

| Dimension | Detail | Source |
|-----------|--------|--------|
| Architecture | Single GCE game server → Cloud SQL (Phoenix) → direct Claude API. Firebase Auth, Cloud Storage. | `architecture/ARCHITECTURE_OVERVIEW.md:60` |
| Scope | Text/voice-to-3D, iterative refinement, first-person exploration, local persistence. **No** multiplayer/VR/mobile/accounts. | `scope/MVP_SCOPE_DOCUMENT.md:18` |
| Infra cost (monthly, est.) | $1,200 – $5,700 | `costs/COST_MODEL.md:25` |
| Platform | PC Desktop (Windows/macOS) | `scope/MVP_SCOPE_DOCUMENT.md:24` |

**Build milestones:** M1 first AI asset (wk 4) → M2 scene composition (wk 8) → M3 NL refinement (wk 10) → M4 playable demo (wk 14) → M5 60 FPS target (wk 16). Detail: `scope/MVP_SCOPE_DOCUMENT.md:94`.

---

### 🚦 Gate 1 → 2 (after PoC)

Decision criteria from `scope/MVP_SCOPE_DOCUMENT.md:114`.

**GO to Phase 2 if ALL hold:**
- All Phase 1 success metrics achieved (gen latency < 30s, asset quality ≥ 7/10, 80% flow completion, 90% voice intent, < 3 refinement cycles)
- Test users express genuine interest (qualitative)
- AI generation quality competitive with existing tools (Blockade Labs, Luma)
- Team confidence in scaling the architecture

**NO-GO if ANY hold:**
- Generation latency > 2 min for simple objects
- Asset quality consistently < 5/10
- Users prefer manual tools over AI assistance
- Core tech infeasible on consumer hardware

**Decision to make at this gate:**
- **Production engine** — Phase 1 runs on Unity ([ADR-0001](adr/0001-engine.md)). Decide here whether to continue on Unity or re-platform to UE5.5 for production fidelity/native-server scale, using PoC evidence. Keep the AI pipeline engine-agnostic so this stays a thin-layer decision, not a rewrite.

---

## Phase 2 — Alpha

**Goal:** Validate market demand — prove people will use OASIS socially and return regularly.

| Dimension | Detail | Source |
|-----------|--------|--------|
| Architecture | GKE Autopilot, 3 regions, Cloud SQL HA, dedicated MCP server, Redis caching, Cloud CDN. | `architecture/ARCHITECTURE_OVERVIEW.md:90` |
| Scope | User accounts, real-time multiplayer (8–16/world), spatial voice, collaborative building, public gallery, Quest VR port. | `scope/MVP_SCOPE_DOCUMENT.md:150` |
| Infra cost (monthly, est.) | $10,500 – $44,500 (with pixel streaming) | `costs/COST_MODEL.md:60` |
| Platforms | PC Desktop (primary) + Meta Quest (secondary) | `scope/MVP_SCOPE_DOCUMENT.md:155` |

---

### 🚦 Gate 2 → 3 (after Alpha)

The Alpha **success metrics** serve as the entry gate to Phase 3 (`scope/MVP_SCOPE_DOCUMENT.md:171`):

- D7 retention ≥ 30%
- D30 retention ≥ 15%
- Average session length ≥ 20 min
- Social sessions (2+ users) ≥ 40% of sessions

> ⚠️ **Gap:** Explicit NO-GO criteria for Gate 2→3 are not yet defined in the source docs (unlike Gate 1→2). Recommend defining hard stop-conditions before Phase 2 exit — see "Open items" below.

---

## Phase 3 — Production ("The OASIS")

**Goal:** Build a persistent, interconnected virtual world platform.

| Dimension | Detail | Source |
|-----------|--------|--------|
| Architecture | Cloudflare CDN → global L7 LB → regional Agones fleets (NAM/EUR/APAC) + Redis → Cloud Spanner (global). | `architecture/ARCHITECTURE_OVERVIEW.md:134` |
| Scope | All platforms (PC/VR/Quest/mobile-via-streaming), creator-economy marketplace, advanced AI NPCs, live events, enterprise/education. | `scope/MVP_SCOPE_DOCUMENT.md:179` |
| Infra cost (monthly, est., no pixel streaming) | $33K (1K CCU) → $230–650K (10K CCU) | `costs/COST_MODEL.md:87` |
| Platforms | All major | `scope/MVP_SCOPE_DOCUMENT.md:189` |

**30-month success targets:** 2M+ MAU, 400K+ DAU, $10M+ ARR (`scope/MVP_SCOPE_DOCUMENT.md:195`).

---

## Cumulative investment timeline (est.)

From `costs/COST_MODEL.md:157`. Note these cumulative figures span team + infra over a longer horizon and are an **independent estimate** from the per-phase budgets above — the two have not been reconciled (see Open items).

| Milestone | Month | Low | High |
|-----------|-------|-----|------|
| End of Phase 1 (PoC) | 4 | $126K | $306K |
| End of Phase 2 (Alpha) | 16 | $1.53M | $3.28M |
| Phase 3 — Year 2 (1K CCU) | 28 | $5.06M | $11.2M |
| Phase 3 — Year 3 (5K CCU) | 40 | $9.7M | $22.1M |

---

## Cross-phase architectural principles

Carried across all phases (`architecture/ARCHITECTURE_OVERVIEW.md`):

1. **Native client, no pixel streaming** — Unity for the PoC ([ADR-0001](adr/0001-engine.md)); production engine re-evaluated at Gate 1→2. No pixel streaming — it's the dominant cost driver; native rendering only. (`costs/COST_MODEL.md:105`)
2. **MCP-based AI integration** — direct Claude API at PoC, dedicated MCP server from Alpha onward.
3. **GCP-native** — leverages existing TROZLAN/Phoenix infrastructure.
4. **Progressive scaling** — each phase's architecture is a superset of the prior; no throwaway rebuilds.

---

## Open items (to resolve before each gate)

- [ ] **Define Gate 2→3 NO-GO criteria** — Phase 2 has success metrics but no explicit stop-conditions (Phase 1 has both).
- [ ] **Reconcile budget figures** — per-phase budgets (`scope`: ~$400K / ~$2.6M / ~$45M) vs cumulative timeline (`costs`: $126K–$306K / $1.53M–$3.28M / …) are independent estimates that don't currently tie out. Pick one canonical model.
- [ ] **Reconcile break-even table** — `costs/COST_MODEL.md:123` break-even figures don't reconcile with the per-CCU cost tables above them.

---

## Related documents

| Doc | Covers |
|-----|--------|
| `architecture/ARCHITECTURE_OVERVIEW.md` | Per-phase system architecture & tech decisions |
| `scope/MVP_SCOPE_DOCUMENT.md` | Per-phase features, milestones, success metrics, gate criteria |
| `costs/COST_MODEL.md` | Per-phase infrastructure & team cost estimates |
| `adr/0001-engine.md` | Engine decision: Unity for PoC, production engine deferred to Gate 1→2 |

---

*All forward-looking figures are ESTIMATES. Review cycle: at each phase gate.*
