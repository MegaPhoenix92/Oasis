# ADR-0001: Game Engine for the Phase 1 PoC

**Status:** Accepted
**Date:** 2026-05-30
**Decision makers:** Chris (TROZLAN)
**Resolves:** [#4 — Engine Selection: Evaluate UE5.5 vs Unity](https://github.com/MegaPhoenix92/Oasis/issues/4)

---

## Context

The README, `CLAUDE.md`, and `ARCHITECTURE_OVERVIEW.md` all asserted **Unreal Engine 5.5** as the chosen client/server engine, while issue #4 remained open and treated the engine as undecided. That is a contradiction: the docs front-ran a decision that was never formally made or recorded. This ADR resolves it.

The decision is scoped to **Phase 1 (PoC)**. The PoC's purpose is to validate one hypothesis — *can a user turn a text prompt into a placeable 3D object in the world in seconds?* (issue #9: prompt → Claude → Meshy → import → place, target < 90s, ≥ 80% success). The engine choice should optimize for **proving that loop fast**, not for the Phase 3 fidelity ceiling.

### Forces specific to this project

1. **The core loop is runtime import of AI-generated glTF assets** (#6 Meshy → #7 import → #9 place). This is the single most-exercised code path in the PoC.
2. **The builders are AI agents** — issues are tagged `delegate:claude`, `delegate:gemini`, `delegate:codex`. Codegen quality depends heavily on the engine's language/ecosystem.
3. **Solo operator + AI agents, PC desktop (Windows/macOS), fast iteration** required (`scope/MVP_SCOPE_DOCUMENT.md`).
4. **PoC may be throwaway** — Phase 2/3 can re-platform if the evidence justifies it.

---

## Decision

**Adopt Unity for the Phase 1 PoC.** The production engine decision is **explicitly deferred to Gate 1→2** and will be made with PoC evidence in hand (see `docs/ROADMAP.md`).

### Why Unity over UE5.5 for the PoC

| Factor | Unity | UE5.5 |
|--------|-------|-------|
| **Runtime glTF import** (core loop) | First-class — `glTFast` is Unity-supported, built for runtime loading | No robust built-in runtime importer; requires third-party plugin (e.g. glTFRuntime) |
| **AI-agent codegen** | C# — strong Codex/Gemini output, large training corpus | C++/Blueprint — weaker, more agent friction |
| **Iteration speed (solo)** | Lighter, faster compile/play loop | Heavier editor, longer cycles |
| **macOS dev parity** | Strong | Windows-primary, macOS second-class |
| **Max visual fidelity** | Good (HDRP) | Best-in-class (Nanite/Lumen) ← *UE's edge* |
| **Native dedicated servers at scale** | Headless build, works with Agones | Native, mature ← *UE's edge* |

For the PoC, the top three rows (runtime glTF, agent codegen, iteration) are decisive and dominate the two rows where UE5.5 leads — both of which matter most at **production scale (Phase 3)**, not during hypothesis validation.

---

## Consequences

**Positive**
- The core loop (#6/#7/#9) builds on a first-class runtime glTF path, de-risking the highest-uncertainty work.
- AI-agent delegation (#5/#6/#7/#8) targets C#, the agents' stronger language.
- Faster solo iteration; clean macOS development.

**Negative / risks**
- **PoC→production re-platform risk.** If Gate 1→2 selects UE5.5 for production fidelity, Phase-1 Unity code is largely throwaway. *Mitigation:* keep the AI pipeline (Claude/Meshy orchestration, asset schema, prompt structuring) **engine-agnostic** so only the thin rendering/scene layer is engine-bound.
- **Fidelity ceiling** is lower than UE5.5. *Acceptable:* the PoC validates the AI hypothesis, not the visual ceiling.
- Infra docs assume Agones + headless servers — valid for Unity headless builds; no infra change required.

**Follow-up actions**
- Close #4 with a link to this ADR.
- Reconcile engine references in README, `CLAUDE.md`, `ARCHITECTURE_OVERVIEW.md`, and `ROADMAP.md` (UE5.5 → Unity for PoC).
- Add "production engine selection" as an explicit Gate 1→2 decision item in `ROADMAP.md`.

---

## Alternatives considered

- **Ratify UE5.5** (keep one engine for all phases, avoid re-platform). Rejected for the PoC because it puts maximum friction (runtime glTF + C++ agent codegen) on the highest-uncertainty path, slowing the very validation the PoC exists to do. Remains a live option for production at Gate 1→2.
- **Web (three.js / react-three-fiber)** — trivial runtime glTF, fastest possible iteration. Rejected: the OASIS vision and the dedicated-server architecture target a native client; a web spike would validate the AI loop but not the platform shape.
- **Timeboxed dual spike** — build #9 in both, then decide. Rejected as too slow for a solo PoC when the analysis already points clearly to Unity; the spike's value is recovered by treating Phase 1 itself as the evidence-gathering exercise for the Gate 1→2 production decision.

---

*Supersedes the implicit UE5.5 assumption in the initial project docs (commit `6f91e99`).*
