---
name: improving-design
description: Atomic node that dispatches N parallel read-only subagents with orthogonal perspectives (grounded in the actual codebase) to critique and refine a design document, then synthesizes findings into Must-Fix, Trade-Off, and Defer buckets and updates the Decision Log.
---

# Improving Design (Parallel N-Agent Atomic Node)

## Purpose

Replace slow sequential `"any suggestion to improve this design"` loops with a **single parallel fan-out** of `N` independent subagents, each with isolated context and read-only access to the real codebase.

## Depth Mapping (`D0-D3`)

Select the agent roster according to the active `D` level (or user override, e.g. `N=4`):

- **D0:** Skip this skill entirely.
- **D1 (2 Parallel Agents):**
  1. `Free-Form Generalist` (pure `"any suggestion to improve this design"` — catches blind spots outside preset lenses)
  2. `Legacy Compatibility & Regression`
- **D2 (3 Parallel Agents — Default for most legacy tasks):**
  1. `Free-Form Generalist`
  2. `Legacy Compatibility & Regression`
  3. `Minimal Diff & Isolation Seam`
- **D3 (5 Parallel Agents — High design uncertainty / core legacy refactor):**
  1. `Free-Form Generalist`
  2. `Legacy Compatibility & Regression`
  3. `Minimal Diff & Isolation Seam`
  4. `Legacy Testability & Verification`
  5. `YAGNI & Complexity Pruning`

## Process

### 1. Prepare Inputs
Collect:
- `DESIGN_PATH`: exact path to the design document.
- `KEY_FILES`: 3-10 existing repository files touched or called by this design.
- `REPO_MODE`: `Legacy` or `Greenfield`.

### 2. Dispatch All `N` Agents in ONE Turn (Parallel Fan-Out)
- Issue all `N` subagent dispatches **in the same response** so they execute concurrently (following `dev-workflow:dispatching-parallel-agents`).
- Fill each subagent's prompt from `perspectives.md` in this directory.
- **Critical Rule:** Every subagent receives isolated context (never paste your conversation history) and is explicitly instructed to perform **read-only codebase inspection** (`git grep`, reading `KEY_FILES`) to verify whether the design's assumptions match reality.
- **Fallback (No Subagent Tool Available):** If the current harness cannot spawn subagents, explicitly state that and run the selected perspectives sequentially in a structured self-critique pass, clearly marking it as a single-context fallback.

### 3. Synthesize & Deduplicate (Main Agent)
Once all `N` agents return:
1. **Merge overlapping points** (note when multiple perspectives independently flagged the same issue — high-confidence signal).
2. **Discard ivory-tower noise** that contradicts verified codebase facts or violates explicit Non-Goals.
3. **Classify every remaining item into 3 buckets:**
   - **Must-Fix (Objective Defect / Verified Codebase Mismatch):** Clear bugs, missed callers, broken invariants, missing rollback, or contradictions with existing code.
   - **Trade-Off (Requires Human Decision):** Legitimate architectural alternatives where your human partner should choose. Present concrete options with pros/cons and your recommendation.
   - **Nice-to-Have / Defer:** Polish or future ideas; do NOT bloat the current design — either drop or log in Non-Goals.

### 4. Present & Apply Updates
- Present the synthesized 3-bucket summary concisely to your human partner.
- If there are **Trade-Off** items, wait for their decision before finalizing.
- If there are only **Must-Fix** items (and they are clear), apply them directly or confirm briefly, then:
  1. Update `DESIGN_PATH` in place.
  2. Append every adopted change AND every intentionally rejected major suggestion to **Section 8: Decision Log** (so PR reviewers see what was considered and why).
  3. Commit the refined design (if tracked in git):
     ```bash
     git add <DESIGN_PATH>
     git commit -m "docs(design): refine <topic> design (D<level>, <N>-agent review)"
     ```

### 5. Optional Round 2 Convergence (`D3` Only)
- If `D3` Round 1 caused a major architectural pivot (e.g., switched Approaches or changed core data contracts), offer ONE targeted Round 2 pass with 2 agents (`Free-Form` + `Legacy Compatibility`) to verify the new design has no fresh holes. Cap at 2 rounds total.

### 6. Handoff
- Once your human partner approves the refined design doc, hand off to `dev-workflow:legacy-impl` (carrying `DESIGN_PATH` and the active `R` level).

## Red Flags

| Thought | Reality |
| :--- | :--- |
| "I'll ask the 5 agents one by one" | Dispatch all `N` in a single turn for true parallelism. |
| "Just give them the design doc, no need to read code" | In legacy repos, design-only critique produces ivory-tower advice. Agents must verify against real code. |
| "Paste all 5 raw agent outputs to the user" | Your job is synthesis: deduplicate, verify against code, and bucket into Must-Fix / Trade-Off / Defer. |
| "Accept every suggestion to be thorough" | Blindly accepting suggestions causes scope creep. Reject or defer anything violating Non-Goals and record why in Decision Log. |
