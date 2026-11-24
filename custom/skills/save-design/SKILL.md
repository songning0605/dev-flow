---
name: save-design
description: Atomic node to persist design consensus into a structured repository document with Current State, Seam, Blast Radius, Rollback, and Decision Log, then commit it cleanly for PR traceability.
---

# Save Design (Atomic Node)

## Purpose

Turn brainstorming consensus into a durable, self-contained design document that:
1. Gives parallel `improving-design` agents concrete claims and file paths to challenge.
2. Gives `legacy-impl` unambiguous scope boundaries (what to touch and what NOT to touch).
3. Gives future PR reviewers full context on **why** each decision was made.

## Process

1. **Determine Output Path (Zero-Config):**
   - Check existing repo directories in order: `docs/designs/`, `docs/rfcs/`, `docs/adr/`, `docs/superpowers/specs/`.
   - Use the first existing directory, or create `docs/designs/` if none exists.
   - Filename: `YYYY-MM-DD-<kebab-case-topic>-design.md`.
   - If the user prefers not to commit design docs into this repo, save to a local path or external link they specify and record that reference for commits/PRs.

2. **Write the Design Document:**
   - Follow `design-template.md` in this directory.
   - Keep it crisp and concrete: real file paths, real function/interface names, exact legacy callers discovered during archeology, and explicit Non-Goals.
   - In **Legacy Mode**, `Current State & Seam`, `Blast Radius & Compatibility`, `Rollback Strategy`, and `Legacy Debt Explicitly Not Touched` are **mandatory**.
   - In **Greenfield Mode**, condense `Current State` to a 1-line note and focus on `Approaches`, `Interfaces`, and `Verification`.

2.5. **Deterministic Design Quality Gate *(Graded Gate: `D0` exempt; `D >= 1` or `Legacy Mode` mandatory)*:**
   - When `D >= 1` or in `Legacy Mode`, you **MUST** run `python <plugin-root>/scripts/check-design.py <design-doc-path> --raw "<original user request>"` before committing.
   - Fix every reported `ERROR` (missing Legacy sections, leftover placeholders, or verbatim raw-prompt echo in `Intent & Why`), write the returned `design_basis_hash` into `Basis Hash`, and print one visible receipt line: `[Design Gate] PASS | hash=<16-hex> | scope_files=<N>` (emit `[Design Gate] SKIP (no python)` **only** if Python 3 is unavailable).

3. **Commit the Design Doc (if stored in repo):**
   ```bash
   git add <design-doc-path>
   git commit -m "docs(design): add <topic> design"
   ```
   (Only commit if on a working branch or with user consent; never push automatically.)

4. **Handoff:**
   - Report the saved path and current calibrated depth (`D<x> / R<y>`).
   - If `D >= 1`, proceed directly to `dev-workflow:improving-design` with `<design-doc-path>` and the list of key legacy files touched.
   - If `D == 0`, proceed directly to `dev-workflow:legacy-impl` (after user approval of the design doc).
