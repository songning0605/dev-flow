---
name: retro-evolve
description: Optional atomic self-evolution node (Plan B) that reads a bounded rolling window (last 30 entries) from ~/.agent-plugins/dev-workflow-metrics.jsonl, applies strict recurrence and subtraction-first rules, proposes concrete diffs to custom/skills/, verifies via --local-only self-tests, and rotates consumed logs.
---

# Retro-Evolve (Controlled Self-Evolution Node)

## Purpose

Continuously calibrate `dev-workflow` (D/R thresholds, parallel review perspectives, legacy guardrails, and Red Flags) using real evidence from completed tasks — **without** prompt bloat, single-project overfitting, or uncontrolled silent self-modification.

## When to Invoke

- Explicitly invoked by the user (e.g. "run `dev-workflow:retro-evolve`").
- Recommended cadence: after every **10–15 completed tasks** (or after a painful production/review miss).

## The 3 Iron Laws of Controlled Evolution

1. **Recurrence Gate (Anti-Overfitting):** Never propose a global rule for a one-off quirk. A friction pattern, escalation trend, or blind spot MUST recur across **at least 2–3 tasks** in the metrics window (or be explicitly requested by the user as a permanent rule).
2. **Subtraction-First (Anti-Bloat):** Before adding any new rule, Red Flag, or perspective prompt line, check whether an obsolete, redundant, or zero-hit rule/perspective can be pruned or merged so total skill length stays lean.
3. **Source-Only + Human Approval + Automated Gate:** Propose changes **only** to `custom/skills/` (never directly edit built `skills/`). Wait for explicit user approval before applying, then validate via `scripts/sync-upstream.py --local-only`.

## Process

### Step 1: Read Bounded Rolling Window (Never Full History)
Run the plugin's bounded reader (max 30 recent entries):
```bash
python <plugin-root>/scripts/log-metric.py tail -n 30
```
If fewer than 3 entries exist, tell the user there isn't enough evidence yet unless they want to make a direct manual tweak.

### Step 2: Analyze Patterns Across 4 Signals
1. **D/R Calibration Drift:** Are `init_d -> final_d` or `init_r -> final_r` frequently escalated? If yes, propose tightening the corresponding axis scoring signal in `custom/skills/dev-workflow/SKILL.md`.
2. **Parallel Perspective ROI:** Which `hit_perspectives` (`free-form`, `legacy-compat`, `minimal-diff`, `testability`, `yagni`) consistently produce high-value findings vs. zero hits across 10+ runs? Propose refining or swapping low-ROI prompts in `custom/skills/improving-design/perspectives.md`.
3. **Design Misses & Escalation Patterns:** Recurring `missed_by_design=true`, `SCOPE_EXPANDED`, `DESIGN_DEVIATION`, or `NO_CHAR_TEST` -> propose targeted checklist additions in `save-design/design-template.md`, `legacy-impl/SKILL.md`, or `deep-review/review-checklist.md`.
4. **Recurring `friction_tags`:** Group identical/similar tags appearing >= 2 times and distill into 1 crisp Red Flag or process adjustment.

### Step 3: Present Concise Evolution Proposal (Max 3 Changes)
Show the user:
- **Evidence Summary:** 3–5 bullet stats from the window (run count, escalation rate, top/bottom perspectives, recurring tags).
- **Proposed Changes (<= 3 per retro):** Exact target file under `custom/skills/`, concrete diff, rationale, and what (if anything) is being removed/simplified.

Wait for explicit user approval ("apply all", "apply #1 only", or "cancel").

### Step 4: Apply, Verify, Rotate & Commit
After user approval:
1. Edit only the approved files under `<plugin-root>/custom/skills/`.
2. Rebuild and run all automated checks offline:
   ```bash
   python <plugin-root>/scripts/sync-upstream.py --local-only
   ```
3. Rotate consumed metrics so the active file stays tiny:
   ```bash
   python <plugin-root>/scripts/log-metric.py rotate --keep 10
   ```
4. Show `git -C <plugin-root> diff --stat` and offer/create a clean revertible commit:
   ```bash
   git -C <plugin-root> add -A
   git -C <plugin-root> commit -m "chore(evolve): <concise summary of calibration>"
   ```
