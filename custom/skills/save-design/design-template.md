# Design: <Topic>

- **Date:** YYYY-MM-DD
- **Mode:** Legacy / Greenfield
- **Intent:** `feature` | `bug` | `refactor` | `analysis`
- **Calibrated Depth:** Design `D<0-3>` | Review `R<0-3>`
- **Basis Hash:** `<populated by check-design.py>`
- **Status:** Draft | Refined | Approved

> 章节标题可中英任意：`## 1. 意图与原因`、`## 2. 目标与非目标`、`## 3. 现状与隔离接缝`、`## 4. 候选方案`、`## 5. 详细设计与接口`、`## 6. 影响面、兼容性与回滚`、`## 7. 验证与测试策略` 与下方英文标题等价（`check-design.py` 同义映射）。

## 1. Intent & Why
What problem are we solving and why now? What does success look like?

## 2. Goals, Non-Goals & Anti-Goals
- **Goals:** ...
- **Non-Goals (Explicitly Out of Scope / Legacy Debt Not Touched):** ...
- **Anti-Goals (What would make this a failure even if tests pass):** ...

## 3. Current State & Isolation Seam *(Mandatory in Legacy Mode)*
- **Existing Flow & Key Files:** `path/to/file.ext` (list verified callers, entry points, cron/MQ/config hooks)
- **Hidden Invariants / Legacy Contracts:** ...
- **Planned Seam:** Where new logic attaches so legacy code changes stay minimal.

## 4. Approaches Considered
| Approach | Summary | Pros | Cons / Risks | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| Option A | ... | ... | ... | Selected / Rejected |
| Option B | ... | ... | ... | Selected / Rejected |

**Why Selected:** ...

## 5. Detailed Design & Interfaces
- **Files to Create:** `...`
- **Files to Modify (Scope Lock):** `...`
- **Key Interfaces / Data Contracts / State Transitions:** ...

## 6. Blast Radius, Compatibility & Rollback
- **Affected Callers / Consumers:** ...
- **Backward Compatibility & Dirty Data Handling:** ...
- **Rollback Strategy:** How to revert safely (feature flag / reversible migration / code revert).

## 7. Verification & Test Strategy
- **Characterization Tests (Lock Existing Legacy Behavior):** ...
- **New Behavior Tests (TDD RED->GREEN):** ...
- **Manual / Integration Checks:** ...

## 8. Open Questions *(Must Be Empty or Explicitly Deferred)*
| Question | Status | Resolution / Deferral Reason |
| :--- | :--- | :--- |
| ... | Answered / Deferred-to-prototype / Deferred-to-impl | ... |

An entry here means the design is **not** approved yet: either answer it in one round of questions, or register a deferral with the concrete probe (`Deferred-to-prototype` — look/feel questions only a throwaway build settles) or the later gate that will decide it (`Deferred-to-impl`). "Everyone knows" / "obvious" is not a resolution.

## 9. Decision Log *(Append-Only for PR Reviewers)*
| Date | Source | Decision / Trade-off | Rationale |
| :--- | :--- | :--- | :--- |
| YYYY-MM-DD | Brainstorm | ... | ... |
