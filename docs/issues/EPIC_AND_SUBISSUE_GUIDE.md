# Agent Guide: Creating Epics & Sub-Issues

**Audience:** AI agents (Claude / Codex / Gemini) and humans managing the Oasis backlog.
**Purpose:** A repeatable, low-fog process for organizing work into **epics → sub-issues** on GitHub, without duplicating the existing backlog.

> **Golden rule:** Issues #1–#9 already exist. **Never recreate them.** Link them as sub-issues of an epic. Only `create` genuinely new work.

---

## 1. The hierarchy

Three levels, using GitHub's **native sub-issues** (parent/child), all tied to a phase in [`../ROADMAP.md`](../ROADMAP.md):

```
Milestone capstone issue  (e.g. #9 "M1 Goal")   ← the phase's falsifiable outcome
  └── [EPIC] Workstream                          ← a coherent slice of work
        └── Task issue (#1, #5, …)               ← a single deliverable, agent-sized
```

- **Epic** = a workstream that groups related tasks. Title prefix `[EPIC]`, label `epic`.
- **Task** = one deliverable an agent can own end-to-end. This is what #1–#9 already are.
- **Milestone capstone** = the issue that proves the phase succeeded (#9 for Phase 1).

---

## 2. Conventions

| Field | Rule |
|-------|------|
| Epic title | `[EPIC] <Workstream Name>` |
| Task title | Imperative, specific (`Integrate Meshy.ai for 3D asset generation`) |
| Phase label | `phase:1` / `phase:2` / `phase:3` — **create these if missing** (see §5) |
| Domain label | Reuse existing: `ai`, `3d`, `engine`, `ui`, `backend`, `infra`, `research`, `integration`, `architecture` |
| Priority | `priority:high` / `priority:medium` |
| Delegation | `delegate:claude` / `delegate:codex` / `delegate:gemini` — assign per the builder's strength |
| Blocking | `status:blocked` when a dependency isn't met |

Every epic body must state: **goal**, **the phase it belongs to**, and a **task checklist** (auto-populated once sub-issues are linked).

---

## 3. Canonical Phase 1 epic map (apply this first)

`#4` is closed (resolved by ADR-0001). Map the remaining open issues under four epics, all rolling up to the **#9 M1 capstone**:

| Epic (create) | Labels | Existing sub-issues (link, don't recreate) |
|---------------|--------|---------------------------------------------|
| `[EPIC] Foundation & Tooling` | `epic, infra, phase:1` | #1 (GCP setup), #2 (dev env) |
| `[EPIC] AI Generation Pipeline` | `epic, ai, phase:1, priority:high` | #3 (3D API research), #5 (Claude integration), #6 (Meshy) |
| `[EPIC] Engine & Scene (Unity)` | `epic, engine, phase:1, priority:high` | #7 (3D scene + import) |
| `[EPIC] Creator Experience` | `epic, ui, phase:1` | #8 (text input UI) |

Then make the four epics **sub-issues of #9** so the M1 goal tree reads top-down.

---

## 4. Commands (copy-paste)

```bash
OWNER=MegaPhoenix92 ; REPO=Oasis

# --- helper: link an existing issue as a sub-issue of a parent ---
# usage: add_sub <parent_number> <child_number>
add_sub() {
  child_id=$(gh api "/repos/$OWNER/$REPO/issues/$2" --jq .id)
  gh api --method POST "/repos/$OWNER/$REPO/issues/$1/sub_issues" \
    -H "X-GitHub-Api-Version: 2022-11-28" -F sub_issue_id="$child_id"
}

# --- create an epic, capture its number ---
url=$(gh issue create --repo "$OWNER/$REPO" \
  --title "[EPIC] AI Generation Pipeline" \
  --label "epic,ai,phase:1,priority:high" \
  --body $'**Phase:** 1 (PoC)\n**Goal:** Text prompt -> structured spec -> generated 3D asset, ready to import.\n\n### Tasks\n(auto-tracked as sub-issues are linked)')
EPIC=${url##*/}   # trailing path segment = issue number

# --- link existing tasks under the epic ---
add_sub "$EPIC" 3
add_sub "$EPIC" 5
add_sub "$EPIC" 6

# --- finally, nest the epic under the #9 M1 capstone ---
add_sub 9 "$EPIC"
```

Repeat the `gh issue create` + `add_sub` block for each epic in §3.

### Fallback (if the sub-issues API is unavailable)
Put a task list in the epic body — GitHub auto-tracks completion and shows a progress bar:
```markdown
### Tasks
- [ ] #3
- [ ] #5
- [ ] #6
```
This is weaker than native sub-issues (no parent/child rollup), so prefer `add_sub`. Use it only as a degraded mode.

---

## 5. One-time label setup

Create the labels this guide relies on if they don't exist yet:
```bash
gh label create epic    --repo "$OWNER/$REPO" --color 5319e7 --description "Epic: groups related task issues" 2>/dev/null
gh label create phase:1 --repo "$OWNER/$REPO" --color 0e8a16 --description "Phase 1 — PoC"          2>/dev/null
gh label create phase:2 --repo "$OWNER/$REPO" --color fbca04 --description "Phase 2 — Alpha"        2>/dev/null
gh label create phase:3 --repo "$OWNER/$REPO" --color b60205 --description "Phase 3 — Production"    2>/dev/null
```
(All other domain/priority/delegate labels already exist.)

---

## 6. Rules for agents

1. **Link, never duplicate.** Before creating any issue, search: `gh issue list --repo $OWNER/$REPO --search "<keywords>" --state all`. If it exists, link it — don't recreate.
2. **One epic = one workstream.** Don't create overlapping epics; a task belongs to exactly one epic.
3. **Every task gets a phase label and a `delegate:*` label.** Unassigned work is invisible work.
4. **Epics are not worked directly.** They track; the sub-issues hold the actual deliverable and acceptance criteria.
5. **New tasks** are created under an existing epic (or a new epic you create first), then immediately `add_sub`-linked.
6. **Respect the gate (work, not creation).** The full forward backlog now exists (see §7), but Phase 2/3 work is **gated**: don't *start building* Phase 2 issues until Gate 1→2 (#25) passes, or Phase 3 until Gate 2→3 (#47) passes. The `phase:2` / `phase:3` label is the "not yet active" signal. Creating the issues ahead of time is fine (planning visibility); working them out of order is not.

---

## 7. Full backlog (created 2026-05-30)

The complete roadmap backlog now exists on GitHub — built by reconciling an independent Codex design with a Workflow design + completeness critic. Structure:

- **Phase 1 (PoC)** — capstone **#9**; epics **#10–#14** (Foundation, AI Pipeline, Engine & Scene, Creator Experience, World Interaction & Polish) + their tasks.
- **[GATE 1→2] #25** — PoC exit + production-engine decision (Unity-continue vs UE5.5 re-platform, per ADR-0001).
- **Phase 2 (Alpha)** — capstone **#26**; epics **#27–#35** (Accounts, Multiplayer, Spatial Voice, Collaborative Building, Gallery, Quest VR, Alpha Infra, Trust & Safety, Legal/Privacy) + tasks.
- **[GATE 2→3] #47** — Alpha readiness + production transition (incl. the NO-GO criteria the ROADMAP flagged as undefined).
- **Phase 3 (Production)** — capstone **#48**; epics **#49–#56** (Global Infra, Cross-Platform/Streaming, Creator Economy, AI NPCs, Live Events, Enterprise/Education, Observability/SRE/DR, Localization) + tasks.
- **Cross-cutting** — epic **#65** Roadmap, Budget & Repo Hygiene + tasks (budget/break-even reconcile, CI, .env.example, Git LFS, test+secrets strategy).

Each maps to features in [`../scope/MVP_SCOPE_DOCUMENT.md`](../scope/MVP_SCOPE_DOCUMENT.md) and phases/gates in [`../ROADMAP.md`](../ROADMAP.md). New work attaches under the relevant existing epic via `add_sub` (§4).

---

## 8. Bootstrap checklist (completed 2026-05-30)

- [x] Labels created (§5) — incl. `epic`, `phase:1/2/3`, `gate`
- [x] Phase-1 epics created and linked under #9 (§3)
- [x] #1–#8 linked under the right epics via `add_sub` (§4) — none recreated
- [x] Full forward backlog created (§7): 23 epics, 2 gates, 3 capstones, ~40 tasks
- [x] Every task carries a `phase:*` + `delegate:*` label

Ongoing rule for new work: attach under the relevant existing epic via `add_sub`; never recreate existing issues.

---

*Keep this guide and the live GitHub issues as the single source of truth — do not mirror the backlog into other Markdown/JSON files.*
