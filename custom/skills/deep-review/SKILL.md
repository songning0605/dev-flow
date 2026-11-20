---
name: deep-review
description: Atomic Review & PR Delivery node with adjustable depth (R0-R3), automatic escalation on implementation risk signals, legacy diff-hygiene & regression auditing, and automatic Design Doc + Decision Log attachment to PRs.
---

# Deep Review & PR Delivery (Atomic Node)

## Purpose

Make `Review` a first-class, adjustable quality gate equal in importance to `Improve Design`, and ensure every PR carries its Design Doc and Decision Log for human reviewers.

## Step 1: Check Auto-Escalation Before Reviewing

Inspect the signals passed from `legacy-impl` (or run `git diff --name-only <BASE_SHA>..<HEAD_SHA>` against `DESIGN_PATH`):
- If `SCOPE_EXPANDED`, `DESIGN_DEVIATION`, or `NO_CHAR_TEST` is true:
  - `R0 -> R1`
  - `R1 -> R2`
  - `R2 -> R3` (if 2+ signals triggered)
- Announce any escalation in one line: e.g. `触发自动升档：Review R1 -> R2（原因：修改了 Design 范围外的 2 个存量文件）。`

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
  - Dispatch **3 parallel fresh read-only whole-branch reviewers** in one turn over `BASE_SHA..HEAD_SHA`:
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

Verify every commit or the PR body clearly links the design so reviewers never have to reverse-engineer intent from raw diffs.
