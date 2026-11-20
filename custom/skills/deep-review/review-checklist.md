# Legacy-Aware Code Review Checklist

Attach this checklist to reviewer subagents alongside `DESIGN_PATH` and `BASE_SHA..HEAD_SHA`.

## 1. Diff Hygiene & Scope Lock
- [ ] Every modified file is justified by `DESIGN_PATH` or an explicit `Ruling:`.
- [ ] Zero unrelated formatting churn, drive-by renames, or unrequested refactoring of legacy code.
- [ ] Commit messages include `Design: <path-or-url>` footer (if repo convention allows).

## 2. Design & Decision Compliance
- [ ] Implementation matches the selected Approach and Interfaces in `DESIGN_PATH`.
- [ ] Non-Goals and Anti-Goals were respected.
- [ ] Any `Ruling:` deviations from the design are sound and clearly explained.

## 3. Legacy Compatibility & Failure Modes
- [ ] Existing callers/consumers remain backward-compatible (or migration path is explicitly handled).
- [ ] Null, empty, or legacy dirty data inputs do not crash or silently corrupt state.
- [ ] Rollback path is viable (no irreversible destructive change without safeguard).

## 4. Test Safety Net
- [ ] Existing legacy behavior modified by this branch is pinned by Characterization Tests.
- [ ] New behavior is covered by real-behavior tests (not mock-only assertions).
- [ ] Full relevant test suite passes with real command output.
