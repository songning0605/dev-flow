---
name: dev-workflow
description: Self-contained atomic R&D workflow orchestrator (Brainstorm -> Save Design -> Improve Design -> Impl -> Review) with zero-config repo detection and independent auto-calibrated depth dials for Improve Design (D0-D3) and Review (R0-R3).
---

# Dev Workflow (Self-Contained Atomic Orchestrator)

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific review or implementation task, ignore this skill.
</SUBAGENT-STOP>

This skill is self-contained and project-independent. It does **not** depend on repository-level `CLAUDE.md` or `AGENTS.md` files. It coordinates five atomic nodes and bundles all required core engineering skills under `dev-workflow:` with zero external plugin dependencies.

## The 5 Atomic Nodes

Every non-trivial engineering task is composed from up to 5 independent, atomic nodes:

1. **Brainstorm** (`dev-workflow:brainstorming` + Legacy Archeology rules below)
2. **Save Design** (`dev-workflow:save-design`)
3. **Improve Design** (`dev-workflow:improving-design`)
4. **Impl** (`dev-workflow:legacy-impl` — wraps `dev-workflow:executing-plans` / `dev-workflow:subagent-driven-development`)
5. **Review** (`dev-workflow:deep-review` — wraps `dev-workflow:requesting-code-review` / `dev-workflow:finishing-a-development-branch`)
6. **Retro-Evolve *(Optional Periodic Node)*** (`dev-workflow:retro-evolve` — analyzes bounded rolling metrics in `~/.agent-plugins/dev-workflow-metrics.jsonl` to propose evidence-backed refinements to `custom/skills/`)

**Atomic Rule:** Any node can be invoked standalone (e.g., "run Improve Design on `docs/designs/foo.md`", or "jump straight to Impl + Review for this small fix").

**Override over `dev-workflow:brainstorming`:**
Ignore the rule in `dev-workflow:brainstorming` that forces jumping directly to `dev-workflow:writing-plans` after design approval. After brainstorming reaches consensus, hand off to `dev-workflow:save-design`, then `dev-workflow:improving-design` (if `D >= 1`), then `dev-workflow:legacy-impl`.

## Step 1: Zero-Config Repo Detection (Run Silently First)

Before asking questions or proposing a workflow, run a **Fast Probe Cap (max 2-3 lightweight read-only commands)** — do NOT deep-read business source files in Step 1 (deep reading belongs inside Brainstorm or Impl):

1. **Legacy / Brownfield vs. Greenfield:**
   - Check `git rev-list --count HEAD 2>/dev/null` and top-level source layout.
   - If the repo has existing commit history and production code -> activate **Legacy Mode** automatically.
   - Otherwise -> **Greenfield Mode**.
2. **Design Doc Location Convention:**
   - Check if any of these directories already exist: `docs/designs/`, `docs/rfcs/`, `docs/adr/`, `docs/superpowers/specs/`.
   - Reuse the existing directory if found; otherwise default to `docs/designs/YYYY-MM-DD-<topic>.md`.
3. **PR & Test Conventions:**
   - Check for `.github/PULL_REQUEST_TEMPLATE.md` (or `.gitlab/merge_request_templates/`) and the project's test runner.

Never ask the user to configure these unless the repo has conflicting conventions.

## Step 2: Dual-Axis Auto-Calibration (`D0-D3` & `R0-R3`)

**Core Principle:** `Improve Design` and `Review` are **equally important, independent first-class dials**. A deep design does not eliminate code review, and a heavy review does not excuse a sloppy design. Calibrate both independently from the task and codebase signals.

### Axis A: Design Uncertainty -> `Improve Design` Depth (`D0-D3`)

Score +1 for each signal present:
- Requirements or acceptance boundaries are ambiguous or have multiple valid approaches.
- Change crosses module/service boundaries, alters public interfaces, or touches persistent schema/data formats.
- Legacy Mode: target area has high coupling, hidden callers, or needs an isolation seam (Adapter/Facade/Flag).
- Mistake in design would cause expensive rework or painful migration.

| Score | Level | Behavior in `dev-workflow:improving-design` |
| :--- | :--- | :--- |
| **0** (or tiny isolated fix / already-finalized design) | **D0** | Skip `Improve Design` |
| **1** | **D1** | **2 parallel agents** (Free-form + Legacy Compatibility/Regression) |
| **2** | **D2** | **3 parallel agents** (+ Minimal Diff & Isolation Seam) |
| **3-4** | **D3** | **5 parallel agents** (+ Legacy Testability + YAGNI Pruning; optional Round 2 convergence on Critical issues) |

### Axis B: Implementation & Regression Blast Radius -> `Review` Depth (`R0-R3`)

Score +1 for each signal present:
- Touches core business path, concurrency/async state, auth/security, or persistent storage/migrations.
- Legacy Mode: target code lacks existing automated test coverage.
- Expected diff spans multiple files/modules or modifies existing legacy functions in place (not isolated in a new module).
- Upfront design was intentionally kept brief (`D0` or `D1`) so correctness relies more on implementation review.

| Score | Level | Behavior in `dev-workflow:deep-review` |
| :--- | :--- | :--- |
| **0** (docs/config/trivial 1-line fix) | **R0** | Automated test verification + self-check only |
| **1** | **R1** | **1 fresh read-only whole-branch reviewer** (Design alignment + Diff hygiene) |
| **2** | **R2** | **Key-checkpoint review + full whole-branch review** (adds legacy compatibility, dirty data, test coverage, PR Design attachment) |
| **3-4** | **R3** | **Per-task dual review** (`subagent-driven-development`) + **Parallel Multi-Lens Whole-Branch Final Review** (Spec/Design + Legacy Regression/Diff Hygiene + Concurrency/Security/Rollback) |

### Announce Calibration on Line 1 (First-Line Banner + Route)

Immediately after Step 1 & Step 2 — **as the very first line of your first reply, before starting implementation or deep code reads** — output a compact calibration banner showing mode, `D/R` levels, scoring rationale, and explicit node route (including why any `D0` nodes are skipped), e.g.:
> `[dev-workflow]` Legacy Mode | **Design D3 (5 并发) + Review R2** | 路线：`Brainstorm -> Save Design -> Improve Design -> Impl -> Review`（原因：涉及存量订单状态机且缺少单测；回复如 `D2 R3` 可随时调整）

Or when `D0` skips design stages:
> `[dev-workflow]` Legacy Mode | **Design D0 + Review R1** | 路线：`Impl -> Review`（跳过 Brainstorm/Save/Improve：单文件明确改动；若无表征测试将在 Review 前自动升档至 R2）

If the user specifies levels explicitly (e.g. `"D3 R1"`, `"D0 R3"`, `"skip design"`), obey immediately without arguing.

### Visible Stage Boundary Tag (Required on Todo-less Harnesses like Pi)

Whenever entering a new atomic node, emit one visible single-line stage header at the start of your message (e.g. `[Stage: Brainstorm]`, `[Stage: Impl]`, `[Stage: Impl -> Review]`) so the user always sees crisp node transitions even when no todo UI is available.

## Step 3: Mid-Flight Escalation Rules (Automatic Depth Upgrade)

Depth is not frozen at startup. Automatically escalate and notify in one line when runtime evidence demands it:

- **Escalate `D` (`D1/D2 -> D3`)** if Brainstorm archeology uncovers unexpected callers, undocumented state machines, or cross-service side effects.
- **Escalate `R` (`R1 -> R2/R3`)** if `Impl` triggers any of:
  1. Modified files outside the Design Doc's planned file list.
  2. Recorded a `Ruling:` that deviates from the Design Doc.
  3. Could not establish Characterization Tests before editing legacy logic.

Never silently downgrade `D` or `R` without user confirmation.

## Legacy Mode Guardrails (Applied Across All Nodes)

When Legacy Mode is active:
1. **Archeology Before Ideation (Brainstorm):** Trace callers/callees, implicit entry points (cron/MQ/hooks/config), and recent `git log` before proposing approaches.
2. **Boundary & Rollback Contract (Save Design):** Document Current State, Isolation Seam, Blast Radius, Backward Compatibility, Rollback Plan, and Non-Goals (legacy debt explicitly NOT touched).
3. **Codebase-Grounded Critique (Improve Design):** Parallel review agents MUST read relevant legacy files (read-only) to falsify design assumptions rather than critiquing in a vacuum.
4. **Characterization Tests + Strict Scope Lock (Impl):** Lock existing legacy behavior with Characterization Tests before editing; apply strict RED->GREEN TDD to new logic; **never** refactor or reformat untouched legacy code. Append `Design: <path-or-url>` to implementation commit footers.
5. **Regression & Diff Hygiene + PR Design Link (Review):** Audit diff scope strictly against the Design Doc, verify backward compatibility, and attach the Design Doc link + Decision Summary to the PR description.

## Platform Adaptation

If running on one of these harnesses, read its tool mapping reference in `references/` before dispatching parallel subagents or finishing branches:
- **Codex (App / CLI):** `references/codex-tools.md` (requires `multi_agent = true` in `~/.codex/config.toml` for parallel `improving-design` and `deep-review` R3)
- **Pi Harness:** `references/pi-tools.md` (uses `pi-subagents` if installed; otherwise sequential multi-perspective fallback)

## Red Flags

| Thought | Reality |
| :--- | :--- |
| "Design was D3, so Review can be skipped" | `D` and `R` are independent dials. High design quality reduces rework, not the need to verify the diff. |
| "I need a repo CLAUDE.md to know how to run" | Run Step 1 Zero-Config Repo Detection and decide yourself. |
| "Let me just jump to `writing-plans` right after brainstorming" | Route through `save-design` -> `improving-design` (if `D >= 1`) first. |
| "This old function is ugly, let me clean it up while I'm here" | Strict Scope Lock. Note the smell in the ledger/report; do not pollute the diff. |
