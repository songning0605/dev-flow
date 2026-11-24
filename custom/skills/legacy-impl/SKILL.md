---
name: legacy-impl
description: Atomic implementation node bridging a refined Design Doc to code with legacy-safe Characterization Tests + Incremental TDD, Strict Scope Lock (no boy-scout refactoring), Design commit footers, and automatic Review escalation signals.
---

# Legacy-Safe Impl (Atomic Node)

## Purpose

Execute the approved Design Doc cleanly with minimal friction when design is already thorough, while protecting legacy codebases from scope creep and regressions.

## Execution Mode Routing

Choose the lightest execution mechanism that matches the active `R` level and task structure:

1. **Lightweight Inline Mode (Default when `D >= 2` and `R <= 2`, or <= 3 cohesive tasks):**
   - If the Design Doc already specifies exact files, interfaces, and test cases, skip writing a bloated line-by-line plan transcript.
   - Maintain a lightweight task checklist/ledger and execute task-by-task following `dev-workflow:executing-plans` discipline (real test evidence, explicit `Ruling:` on any deviation).
2. **Structured Plan + Subagent Mode (When `R == 3`, or > 4 independent tasks):**
   - Invoke `dev-workflow:writing-plans` (referencing `**Spec:** <DESIGN_PATH>`) -> `dev-workflow:subagent-driven-development`.
   - Pass the **Strict Scope Lock** and **Commit Footer** rules below into every implementer dispatch.

## Legacy Implementation Rules (Mandatory in Legacy Mode)

### 1. Characterization Tests + Incremental TDD
Adapt `dev-workflow:test-driven-development` for brownfield realities without losing safety:
- **Modifying Existing Legacy Logic:** First write a **Characterization Test** that captures and passes (GREEN) on the current production behavior. This is your regression safety net. Only then modify behavior.
- **New Functions / Isolated Seam Modules:** Follow strict **RED -> GREEN -> REFACTOR** TDD (`dev-workflow:test-driven-development`).
- **Legacy Boundary Mocks:** Stubs/mocks are permitted **only** at explicit legacy boundaries (external network calls, global singletons, un-injectable legacy DB handles) and must be noted briefly.

### 2. Strict Scope Lock (Overrides Boy-Scout Refactoring)
- **ONLY** modify files listed in the Design Doc's `Files to Modify` / `Files to Create`.
- **DO NOT** reformat untouched lines, rename unrelated legacy variables, or "clean up" nearby ugly code.
- If you discover a genuine bug or tech debt outside scope, record it under `Out-of-Scope Notes` in your ledger/report — do not fix it in this branch.
- If you MUST edit an unlisted file to make the design work, record a `Ruling: <file> — <why required> — <risk>` and flag an **Escalation Signal**.

### 3. Design Traceability in Every Commit
Include the Design Doc path (or external link) in the commit message footer:

```text
feat(<scope>): <concise summary>

<optional short body>

Design: <relative-path-to-design-doc-or-url>
```

## Escalation Signals to Pass to `dev-workflow:deep-review`

Track these 3 boolean flags during implementation and pass them to `dev-workflow:deep-review`:
1. `SCOPE_EXPANDED`: Edited any file not listed in the Design Doc.
2. `DESIGN_DEVIATION`: Recorded one or more `Ruling:` entries deviating from the Design Doc.
3. `NO_CHAR_TEST`: Modified existing legacy behavior without being able to add Characterization Tests.

Note: If a legacy repo has **no test framework at all** and you modified existing behavior, `NO_CHAR_TEST` is strictly **`true`**.

Before invoking `dev-workflow:deep-review`, you MUST print all 3 flags explicitly in one line so escalation is never dropped:
`[Impl Exit] SCOPE_EXPANDED=<true|false> | DESIGN_DEVIATION=<true|false> | NO_CHAR_TEST=<true|false>`

## Handoff

**Verification Stamp *(Graded Gate: `R0` exempt; `R >= 1` or `Legacy Mode` mandatory)*:** After final tests pass (`dev-workflow:verification-before-completion`), you **MUST** run:
```bash
python <plugin-root>/scripts/verify-basis.py stamp --repo . --design <DESIGN_PATH> --cmd "<test-command>"
```
and print one visible receipt line right after `[Impl Exit]`: `[Verify Stamp] combined=<16-hex> | design=<16-hex> | code=<16-hex>` (emit `[Verify Stamp] SKIP (no python)` **only** if Python 3 is unavailable).

Once all tasks pass verification (`dev-workflow:verification-before-completion`), invoke `dev-workflow:deep-review` with:
- `DESIGN_PATH`
- `BASE_SHA` (branch merge-base) and `HEAD_SHA`
- Active `R` level (`R0-R3`)
- Escalation flags + list of `Ruling:` lines (if any).
