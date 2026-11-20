#!/usr/bin/env python3
"""Cross-platform self-test for standalone dev-workflow plugin (Windows / macOS / Linux)."""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def check_json_files() -> None:
    print("=== 1. Validating JSON manifests & configs ===")
    files = [
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        ".cursor-plugin/marketplace.json",
        ".agents/plugins/marketplace.json",
        ".cursor-plugin/plugin.json",
        ".codex-plugin/plugin.json",
        "gemini-extension.json",
        "package.json",
        "hooks/hooks.json",
        "hooks/hooks-cursor.json",
        "upstream.lock",
        "vendor-manifest.json",
        "custom/patches/patches.json",
    ]
    for rel in files:
        path = PLUGIN_ROOT / rel
        assert path.is_file(), f"MISSING: {rel}"
        json.loads(path.read_text(encoding="utf-8"))
        print(f"OK: {rel}")


def check_skills_frontmatter() -> None:
    print("=== 2. Validating all 18 bundled SKILL.md frontmatters ===")
    manifest = json.loads((PLUGIN_ROOT / "vendor-manifest.json").read_text(encoding="utf-8"))
    expected = sorted(set(manifest["vendored_skills"] + [
        "dev-workflow", "save-design", "improving-design", "legacy-impl", "deep-review", "retro-evolve"
    ]))
    for skill in expected:
        path = PLUGIN_ROOT / "skills" / skill / "SKILL.md"
        assert path.is_file(), f"MISSING: {path}"
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        assert text.startswith("---\n"), f"{skill}: missing frontmatter start"
        end = text.index("\n---\n", 4)
        fm = text[4:end]
        assert f"name: {skill}" in fm, f"{skill}: missing name field"
        assert "description:" in fm, f"{skill}: missing description field"
    print(f"OK: verified all {len(expected)} skills")


def check_no_external_namespace() -> None:
    print("=== 3. Verifying zero leftover 'superpowers:' namespace references ===")
    leaks = []
    for p in (PLUGIN_ROOT / "skills").rglob("*.md"):
        txt = p.read_text(encoding="utf-8")
        if "superpowers:" in txt:
            leaks.append(str(p.relative_to(PLUGIN_ROOT / "skills")))
    assert not leaks, f"Found unrewritten superpowers: references in: {leaks}"
    print("OK: zero external superpowers: references (100% standalone)")


def check_patches() -> None:
    print("=== 4. Verifying legacy & workflow patches took effect ===")
    checks = [
        ("skills/brainstorming/SKILL.md", "dev-workflow:save-design"),
        ("skills/brainstorming/SKILL.md", "Legacy Archeology"),
        ("skills/subagent-driven-development/implementer-prompt.md", "Strict Scope Lock (Legacy Safety)"),
        ("skills/finishing-a-development-branch/SKILL.md", "Design & Key Decisions"),
    ]
    for rel, needle in checks:
        txt = (PLUGIN_ROOT / rel).read_text(encoding="utf-8")
        assert needle in txt, f"Patch verification failed: '{needle}' not found in {rel}"
    print("OK: all patches verified in built skills/")


def run_hook(extra_env: dict) -> str:
    env = os.environ.copy()
    env.update(extra_env)
    hooks_dir = PLUGIN_ROOT / "hooks"
    if platform.system() == "Windows":
        # Run with cwd=hooks_dir so paths containing parentheses/spaces like "foo(1)"
        # never get split by cmd.exe metacharacter parsing.
        cmd = ["cmd.exe", "/d", "/c", "run-hook.cmd", "session-start"]
    else:
        cmd = ["sh", str(hooks_dir / "run-hook.cmd"), "session-start"]
    proc = subprocess.run(cmd, cwd=str(hooks_dir), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    assert proc.returncode == 0, f"Hook failed (rc={proc.returncode}): {proc.stderr}"
    return proc.stdout.strip()


def check_hooks() -> None:
    print("=== 5. Testing SessionStart hook JSON across platforms ===")
    cases = [
        ("Claude Code", {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "CURSOR_PLUGIN_ROOT": "", "COPILOT_CLI": ""}, lambda d: d["hookSpecificOutput"]["additionalContext"]),
        ("Cursor", {"CURSOR_PLUGIN_ROOT": str(PLUGIN_ROOT), "CLAUDE_PLUGIN_ROOT": "", "COPILOT_CLI": ""}, lambda d: d["additional_context"]),
        ("SDK/Copilot", {"CLAUDE_PLUGIN_ROOT": "", "CURSOR_PLUGIN_ROOT": "", "COPILOT_CLI": "1"}, lambda d: d["additionalContext"]),
    ]
    for label, env_patch, extractor in cases:
        out = run_hook(env_patch)
        if not out and platform.system() == "Windows":
            print(f"SKIP ({label}): Git Bash not found on Windows; hook exited cleanly (rc=0). Install Git for Windows to enable SessionStart auto-injection.")
            return
        data = json.loads(out)
        ctx = extractor(data)
        assert "dev-workflow" in ctx, f"{label}: missing dev-workflow in hook output"
        print(f"OK: {label} SessionStart JSON")



def check_pi_extension() -> None:
    print("=== 6. Checking Pi package & extension ===")
    pkg = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "pi-package" in pkg.get("keywords", []), "package.json missing pi-package keyword"
    assert pkg.get("pi", {}).get("extensions") == ["./.pi/extensions/dev-workflow.ts"]
    assert pkg.get("pi", {}).get("skills") == ["./skills"]
    assert (PLUGIN_ROOT / ".pi" / "extensions" / "dev-workflow.ts").is_file()
    assert (PLUGIN_ROOT / "skills" / "dev-workflow" / "references" / "pi-tools.md").is_file()
    print("OK: Pi package.json, .pi/extensions/dev-workflow.ts, and pi-tools.md present")
    # Run Node native test suite if Node >= 22.6 is available
    try:
        ver = subprocess.check_output(["node", "-v"], text=True, encoding="utf-8", errors="replace").strip().lstrip("v")
        major, minor = (int(x) for x in ver.split(".")[:2])
        if (major, minor) >= (22, 6):
            res = subprocess.run(
                ["node", "--test", str(PLUGIN_ROOT / "tests" / "pi" / "test-pi-extension.mjs")],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            assert res.returncode == 0, f"Pi extension test failed:\n{res.stdout}\n{res.stderr}"
            print("OK: node --test tests/pi/test-pi-extension.mjs passed")
        else:
            print(f"SKIP: Node {ver} (< 22.6); skipping TypeScript execution of test-pi-extension.mjs")
    except FileNotFoundError:
        print("SKIP: node not found; skipping test-pi-extension.mjs execution")



def check_codex_adaptation() -> None:
    print("=== 7. Checking Codex App/CLI adaptation & Windows .gitattributes ===")
    codex_pkg = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    iface = codex_pkg.get("interface", {})
    assert iface.get("displayName"), ".codex-plugin/plugin.json missing interface.displayName"
    assert iface.get("composerIcon"), ".codex-plugin/plugin.json missing interface.composerIcon"
    assert iface.get("logo"), ".codex-plugin/plugin.json missing interface.logo"
    assert (PLUGIN_ROOT / iface["composerIcon"]).is_file(), f"Missing icon: {iface['composerIcon']}"
    assert (PLUGIN_ROOT / iface["logo"]).is_file(), f"Missing logo: {iface['logo']}"
    assert (PLUGIN_ROOT / "skills" / "dev-workflow" / "references" / "codex-tools.md").is_file()
    assert (PLUGIN_ROOT / ".gitattributes").is_file()
    print("OK: Codex App/CLI manifest, icons, codex-tools.md, and .gitattributes verified")



def check_plan_b_evolution() -> None:
    print("=== 8. Testing Plan B evolution (review-lenses, log-metric.py, retro-evolve) ===")
    import tempfile
    assert (PLUGIN_ROOT / "skills" / "deep-review" / "review-lenses.md").is_file()
    assert "Fast Probe Cap" in (PLUGIN_ROOT / "skills" / "dev-workflow" / "SKILL.md").read_text(encoding="utf-8")
    assert "[Handoff Gate]" in (PLUGIN_ROOT / "skills" / "deep-review" / "SKILL.md").read_text(encoding="utf-8")
    assert (PLUGIN_ROOT / "skills" / "retro-evolve" / "SKILL.md").is_file()
    logger = PLUGIN_ROOT / "scripts" / "log-metric.py"
    assert logger.is_file()
    with tempfile.TemporaryDirectory(prefix="dw_metrics_") as td:
        mfile = Path(td) / "metrics.jsonl"
        for i in range(4):
            res = subprocess.run(
                [
                    sys.executable, str(logger), "--file", str(mfile), "log",
                    "--repo-mode", "legacy",
                    "--init-d", "D2", "--final-d", "D3",
                    "--init-r", "R1", "--final-r", "R2",
                    "--escalations", "SCOPE_EXPANDED",
                    "--hit-perspectives", "free-form,legacy-compat",
                    "--ruling-count", "1",
                    "--friction-tags", "hidden-caller,legacy-mock",
                ],
                capture_output=True, text=True, encoding="utf-8", check=False,
            )
            assert res.returncode == 0, f"log-metric.py log failed: {res.stderr}"
        tail_res = subprocess.run(
            [sys.executable, str(logger), "--file", str(mfile), "tail", "-n", "2"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        assert tail_res.returncode == 0
        arr = json.loads(tail_res.stdout)
        assert len(arr) == 2 and arr[-1]["final_d"] == "D3"
        rot_res = subprocess.run(
            [sys.executable, str(logger), "--file", str(mfile), "rotate", "--keep", "1"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        assert rot_res.returncode == 0
        remaining = [ln for ln in mfile.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(remaining) == 1
    print("OK: review-lenses.md, retro-evolve, and bounded log-metric.py (log/tail/rotate) passed")


def main() -> int:
    check_json_files()
    check_skills_frontmatter()
    check_no_external_namespace()
    check_patches()
    check_hooks()
    check_pi_extension()
    check_codex_adaptation()
    check_plan_b_evolution()
    print("=== ALL STANDALONE CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
