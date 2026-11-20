#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== 1. Validating JSON manifests & configs ==="
for f in \
  ".claude-plugin/plugin.json" \
  ".cursor-plugin/plugin.json" \
  ".codex-plugin/plugin.json" \
  "gemini-extension.json" \
  "hooks/hooks.json" \
  "hooks/hooks-cursor.json" \
  "upstream.lock" \
  "vendor-manifest.json" \
  "custom/patches/patches.json"; do
  python3 -m json.tool "${PLUGIN_ROOT}/${f}" >/dev/null
  echo "OK: ${f}"
done

echo "=== 2. Validating all 17 bundled SKILL.md frontmatters ==="
python3 - "${PLUGIN_ROOT}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = json.loads((root / "vendor-manifest.json").read_text(encoding="utf-8"))
expected_skills = sorted(set(manifest["vendored_skills"] + [
    "dev-workflow", "save-design", "improving-design", "legacy-impl", "deep-review"
]))

for skill in expected_skills:
    path = root / "skills" / skill / "SKILL.md"
    assert path.is_file(), f"MISSING: {path}"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{skill}: missing frontmatter start"
    end = text.index("\n---\n", 4)
    fm = text[4:end]
    assert f"name: {skill}" in fm, f"{skill}: missing name field"
    assert "description:" in fm, f"{skill}: missing description field"
print(f"OK: verified all {len(expected_skills)} skills")
PY

echo "=== 3. Verifying zero leftover 'superpowers:' namespace references ==="
python3 - "${PLUGIN_ROOT}/skills" <<'PY'
import sys
from pathlib import Path

skills_root = Path(sys.argv[1])
leaks = []
for p in skills_root.rglob("*.md"):
    txt = p.read_text(encoding="utf-8")
    if "superpowers:" in txt:
        leaks.append(str(p.relative_to(skills_root)))
assert not leaks, f"Found unrewritten superpowers: references in: {leaks}"
print("OK: zero external superpowers: references (100% standalone)")
PY

echo "=== 4. Verifying legacy & workflow patches took effect ==="
grep -q "dev-workflow:save-design" "${PLUGIN_ROOT}/skills/brainstorming/SKILL.md"
grep -q "Legacy Archeology" "${PLUGIN_ROOT}/skills/brainstorming/SKILL.md"
grep -q "Strict Scope Lock (Legacy Safety)" "${PLUGIN_ROOT}/skills/subagent-driven-development/implementer-prompt.md"
grep -q "Design & Key Decisions" "${PLUGIN_ROOT}/skills/finishing-a-development-branch/SKILL.md"
echo "OK: all patches verified in built skills/"

echo "=== 5. Testing SessionStart hook JSON across platforms ==="
CLAUDE_OUT=$(CLAUDE_PLUGIN_ROOT="${PLUGIN_ROOT}" CURSOR_PLUGIN_ROOT="" COPILOT_CLI="" "${PLUGIN_ROOT}/hooks/run-hook.cmd" session-start)
python3 -c 'import json, sys; d=json.loads(sys.argv[1]); assert "dev-workflow" in d["hookSpecificOutput"]["additionalContext"]; print("OK: Claude Code SessionStart JSON")' "$CLAUDE_OUT"

CURSOR_OUT=$(CURSOR_PLUGIN_ROOT="${PLUGIN_ROOT}" CLAUDE_PLUGIN_ROOT="" "${PLUGIN_ROOT}/hooks/run-hook.cmd" session-start)
python3 -c 'import json, sys; d=json.loads(sys.argv[1]); assert "dev-workflow" in d["additional_context"]; print("OK: Cursor SessionStart JSON")' "$CURSOR_OUT"

SDK_OUT=$(CLAUDE_PLUGIN_ROOT="" CURSOR_PLUGIN_ROOT="" COPILOT_CLI="1" "${PLUGIN_ROOT}/hooks/run-hook.cmd" session-start)
python3 -c 'import json, sys; d=json.loads(sys.argv[1]); assert "dev-workflow" in d["additionalContext"]; print("OK: SDK/Copilot SessionStart JSON")' "$SDK_OUT"

echo "=== ALL STANDALONE CHECKS PASSED ==="
