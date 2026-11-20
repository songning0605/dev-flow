# Pi Tool Mapping for dev-workflow

Skills speak in platform-neutral actions ("invoke a skill", "dispatch parallel subagents", "track tasks"). On Pi these resolve as follows:

| Action requested by dev-workflow | Pi equivalent |
| --- | --- |
| Invoke an atomic skill (`dev-workflow:<name>`) | Load `skills/<name>/SKILL.md` via `read`, or let the user invoke `/skill:<name>` |
| Dispatch parallel subagents (`improving-design` D1-D3, `deep-review` R3) | Use `subagent` from `pi-subagents` (parallel mode) if installed; otherwise run structured sequential multi-perspective fallback |
| Task tracking / progress ledger | Use an installed todo/task extension if available, otherwise use plan files, `.superpowers/sdd/*/progress.md`, or repo-local `TODO.md` |
| File & shell operations | Pi lowercase built-ins: `read`, `write`, `edit`, `bash`, `grep`, `find`, `ls` |

## Recommended Companion for Parallel Review on Pi

Install `pi-subagents` alongside `dev-workflow` so `improving-design` (2-5 parallel reviewers) and `deep-review` R3 (3 parallel whole-branch lenses) run concurrently with isolated contexts.
