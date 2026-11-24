---
name: deep-review
description: Atomic Review & PR Delivery node with adjustable depth (R0-R3), automatic escalation on implementation risk signals, legacy diff-hygiene & regression auditing, and automatic Design Doc + Decision Log attachment to PRs.
---

# Deep Review & PR Delivery (Atomic Node)

## Purpose

Make `Review` a first-class, adjustable quality gate equal in importance to `Improve Design`, and ensure every PR carries its Design Doc and Decision Log for human reviewers.

## Step 1: Mandatory Visible `[Handoff Gate]` & Auto-Escalation

**HARD RULE — Before dispatching ANY reviewer**, inspect the signals from `legacy-impl` (or `git diff --name-only <BASE_SHA>..<HEAD_SHA>`) and **print this exact gate line visibly**:

```text
[Handoff Gate] SCOPE_EXPANDED=<true|false> | DESIGN_DEVIATION=<true|false> | NO_CHAR_TEST=<true|false> => Effective Review: R<init> -> R<effective>
```

Escalation rules (non-negotiable):
- If a legacy repo has **no test framework** and existing behavior was modified, `NO_CHAR_TEST` is **`true`** (lack of a test runner is the exact reason deeper review is needed, never an excuse to skip escalation).
- If any 1 flag is `true`: `R0 -> R1`, `R1 -> R2`.
- If 2+ flags are `true`: `R1 -> R2`, `R2 -> R3`.
- Never dispatch an `R1` reviewer when `NO_CHAR_TEST=true`.
- **Verification Freshness Check *(Graded Gate: `R0` exempt; `R >= 1` or `Legacy Mode` mandatory)*:** You **MUST** run `python <plugin-root>/scripts/verify-basis.py check --repo . --design <DESIGN_PATH>` and print `[Verify Check] FRESH | combined=<16-hex>` (or `STALE` -> re-run verification tests and re-stamp before concluding review; emit `[Verify Check] SKIP (no python)` **only** if Python 3 is unavailable).

## Step 2: Execute Review by Depth (`R0-R3`)

Use `review-checklist.md` in this directory alongside `dev-workflow:requesting-code-review/code-reviewer.md`.

- **R0 (Minimal):**
  - Run full relevant test suite (`dev-workflow:verification-before-completion`).
  - Quick self-check of `git diff --stat` for stray files.
- **R1 (Lightweight Fresh Review):**
  - Dispatch **1 fresh read-only reviewer subagent** over `BASE_SHA..HEAD_SHA` with `DESIGN_PATH` + `review-checklist.md` (focus: Design alignment + Diff hygiene).
  - Fix Critical/Important findings in one TDD pass; defer Minors to report.
- **R2 (Standard Legacy Review):**
  - Dispatch **1 thorough fresh read-only reviewer subagent** over `BASE_SHA..HEAD_SHA` with `DESIGN_PATH`, `Ruling:` list, and the full `review-checklist.md` (Design alignment + Diff hygiene + Legacy compatibility/dirty data + Characterization test coverage).
  - Fix Critical/Important findings with failing-test-first proof; re-verify full suite.
- **R3 (Deep Multi-Lens Review):**
  - Per-task reviews were already run if `subagent-driven-development` was used.
  - Dispatch **3 parallel fresh read-only whole-branch reviewers** in one turn over `BASE_SHA..HEAD_SHA` using the exact role templates in `review-lenses.md`:
    1. **Lens A — Design & Decision Compliance:** Verifies implementation matches `DESIGN_PATH` and every `Decision Log` / `Ruling:` entry.
    2. **Lens B — Legacy Regression & Diff Hygiene:** Audits diff scope lock, unintended edits to legacy code, backward compatibility, dirty/null data, and characterization tests.
    3. **Lens C — Concurrency, Security & Rollback Readiness:** Audits race conditions, error paths, security boundaries, migrations, and whether rollback actually works.
  - Main agent synthesizes all 3 reports, deduplicates, fixes Critical/Important findings with TDD proof, and runs a scoped verification pass.

*(If the harness has no subagent tool, execute the active lens checklist sequentially as a dedicated read-only self-review pass and explicitly disclose "self-review fallback" in the final report.)*

## Step 3: Finish Branch & Attach Design to PR

Hand off to `dev-workflow:finishing-a-development-branch` to verify tests, present the integration menu (Merge locally / Push & Create PR / Keep branch), and handle cleanup.

**Mandatory PR Enhancement (Option 2: Push and Create PR):**
When creating the PR, always include a `## Design & Key Decisions` section in the PR body (merging cleanly with the repo's `.github/PULL_REQUEST_TEMPLATE.md` if present):

```markdown
## Design & Key Decisions
- **Design Doc:** [<filename>](<relative-path-in-repo-or-external-url>)
- **Workflow Depth:** Design `D<x>` | Review `R<y>`
- **Key Decisions:**
  - <Top 3-5 bullets distilled from the Design Doc's Decision Log & Impl Rulings>
- **Blast Radius & Rollback:** <1-2 lines from Design Doc>
```

**Delivery Report & Scope Audit *(Graded Gate: `R0` exempt; `R >= 1` or `Legacy Mode` mandatory)*:** When preparing PR or delivery handoff, you **MUST** run:
```bash
python <plugin-root>/scripts/gen-report.py --repo . --base <BASE_SHA> --head <HEAD_SHA> --design <DESIGN_PATH> --depth "D<x> / R<y>"
```
and print one visible receipt line: `[Report Gate] changed=<N> | out_of_scope=<M> | noise_excluded=<K> | verify=<FRESH|STALE>` (emit `[Report Gate] SKIP (no python)` **only** if Python 3 is unavailable).

Verify every commit or the PR body clearly links the design so reviewers never have to reverse-engineer intent from raw diffs.

## Step 4: Log Bounded Workflow Metric (Plan B Evolution Input)

After review and PR preparation finish, append **one** compact whitelisted metric line (<= 500 bytes, no code or diffs) to `~/.agent-plugins/dev-workflow-metrics.jsonl` using the plugin's `scripts/log-metric.py`:

```bash
python <plugin-root>/scripts/log-metric.py log \
  --repo-mode <legacy|greenfield> \
  --init-d <D0-D3> --final-d <D0-D3> \
  --init-r <R0-R3> --final-r <R0-R3> \
  --escalations "<comma-separated flags or empty>" \
  --hit-perspectives "<comma-separated perspective IDs that produced Must-Fix/Trade-Off>" \
  --ruling-count <N> \
  --friction-tags "<0-3 short tags, <=32 chars each>"
```

Skip silently if the user opted out of metrics or if Python is unavailable. Never write business code, file paths, or raw user text into `friction-tags`.
