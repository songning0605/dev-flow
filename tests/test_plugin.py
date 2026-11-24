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

        # Negative cases: cross-field invariants must fail cleanly (rc=1, one-line ERROR, no traceback)
        bad_cases = [
            ("D0 with perspectives", ["--init-d", "D0", "--final-d", "D0", "--init-r", "R0", "--final-r", "R0", "--hit-perspectives", "free-form"], "final-d=D0"),
            ("D1 with yagni", ["--init-d", "D1", "--final-d", "D1", "--init-r", "R0", "--final-r", "R0", "--hit-perspectives", "yagni"], "final-d=D1"),
            ("D_ESCALATED without escalation", ["--init-d", "D2", "--final-d", "D2", "--init-r", "R1", "--final-r", "R1", "--escalations", "D_ESCALATED"], "D_ESCALATED requires"),
            ("SCOPE_EXPANDED with downgrade", ["--init-d", "D1", "--final-d", "D1", "--init-r", "R2", "--final-r", "R1", "--escalations", "SCOPE_EXPANDED"], "requires final-r >= init-r"),
        ]
        for label, extra, expected in bad_cases:
            bad = subprocess.run(
                [sys.executable, str(logger), "--file", str(Path(td) / "bad.jsonl"), "log", "--repo-mode", "legacy", *extra],
                capture_output=True, text=True, encoding="utf-8", check=False,
            )
            assert bad.returncode == 1, f"{label}: expected rc=1, got {bad.returncode}"
            assert "Traceback" not in bad.stderr, f"{label}: raw traceback leaked to stderr"
            assert bad.stderr.count("ERROR:") == 1, f"{label}: expected one clean ERROR line, got {bad.stderr!r}"
            assert expected in bad.stderr, f"{label}: the wrong invariant fired ({bad.stderr.strip()})"
            assert not (Path(td) / "bad.jsonl").exists(), f"{label}: invalid metric was still written"
    print("OK: review-lenses.md, retro-evolve, and bounded log-metric.py (log/tail/rotate + 4 invariant rejections) passed")




def check_dsh_fusion_tools() -> None:
    print("=== 9. Testing dsh-dev-hub fusion scripts (repo-recon, check-design, verify-basis, gen-report) ===")
    import tempfile
    for name in ("repo-recon.py", "check-design.py", "verify-basis.py", "gen-report.py"):
        assert (PLUGIN_ROOT / "scripts" / name).is_file(), f"MISSING script: {name}"
    with tempfile.TemporaryDirectory(prefix="dw_fusion_") as td:
        repo = Path(td) / "repo"
        (repo / "src" / "orders").mkdir(parents=True)
        (repo / "node_modules" / "pkg").mkdir(parents=True)
        (repo / "src" / "orders" / "payment_guard.py").write_text(
            "def prevent_duplicate_charge(order_id):\n    return f'guard:{order_id}'\n",
            encoding="utf-8",
        )
        (repo / "node_modules" / "pkg" / "payment_guard.js").write_text("duplicate_charge", encoding="utf-8")

        # 9.1 repo-recon.py: IDF ranking + skip node_modules + intent detection
        recon_res = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "repo-recon.py"), "--repo", str(repo), "--query", "修复 payment_guard 重复扣款 bug", "--json"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        rdata = json.loads(recon_res.stdout)
        assert rdata["intent"] == "bug", f"Expected bug intent, got {rdata['intent']}"
        assert rdata["files"] and rdata["files"][0]["path"] == "src/orders/payment_guard.py"
        assert all("node_modules" not in f["path"] for f in rdata["files"])

        # 9.2 check-design.py: reject raw echo & accept valid design
        bad_design = repo / "bad-design.md"
        bad_design.write_text("# Design: Bad\n- **Mode:** Legacy\n## 1. Intent & Why\n修复 payment_guard 重复扣款 bug\n", encoding="utf-8")
        bad_res = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "check-design.py"), str(bad_design), "--raw", "修复 payment_guard 重复扣款 bug"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        assert bad_res.returncode == 1, "Expected check-design.py to fail on raw echo and missing sections"

        good_design = repo / "docs" / "designs" / "2026-11-22-payment-guard-design.md"
        good_design.parent.mkdir(parents=True, exist_ok=True)
        good_design.write_text(
            "# Design: Payment Guard\n- **Mode:** Legacy\n"
            "## 1. Intent & Why\nEliminate double-charge race conditions caused by non-idempotent webhook retries.\n"
            "## 2. Goals, Non-Goals & Anti-Goals\n- **Goals:** Idempotency key lock\n- **Non-Goals:** Billing UI\n"
            "## 3. Current State & Isolation Seam\n- `src/orders/payment_guard.py`\n"
            "## 4. Approaches Considered\nOption A selected.\n"
            "## 5. Detailed Design & Interfaces\n- **Files to Modify (Scope Lock):** `src/orders/payment_guard.py`\n"
            "## 6. Blast Radius, Compatibility & Rollback\n- **Rollback Strategy:** Revert commit.\n"
            "## 7. Verification & Test Strategy\n- Characterization test + TDD.\n",
            encoding="utf-8",
        )
        good_res = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "check-design.py"), str(good_design), "--raw", "修复 payment_guard 重复扣款 bug", "--json"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        gdata = json.loads(good_res.stdout)
        assert gdata["ok"] is True and len(gdata["design_basis_hash"]) == 16
        assert "src/orders/payment_guard.py" in gdata["scope_files"]

        # 9.2b check-design.py: Scope Lock paths are normalized (Windows separators,
        # leading ./ and line-range suffixes) so gen-report.py cannot false-flag them;
        # placeholders inside fenced code blocks are not warnings.
        norm_design = repo / "norm-design.md"
        norm_design.write_text(
            good_design.read_text(encoding="utf-8").replace(
                "- **Files to Modify (Scope Lock):** `src/orders/payment_guard.py`",
                "- **Files to Modify (Scope Lock):** `src/orders/payment_guard.py:120-145` `./src/orders/payment_guard.py` "
                "`\\src\\orders\\payment_guard.py`\n"
                "```python\n# TODO: placeholder inside a code fence -> must NOT warn\n...\n```",
            ),
            encoding="utf-8",
        )
        norm_res = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "check-design.py"), str(norm_design), "--json"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        ndata = json.loads(norm_res.stdout)
        assert ndata["scope_files"] == ["src/orders/payment_guard.py"], ndata["scope_files"]
        assert ndata["ok"] is True
        assert not [w for w in ndata["warnings"] if "placeholder" in w], ndata["warnings"]

        # 9.2c a stale/never-refreshed header Basis Hash must fail the gate (this is what
        # makes improving-design's "refresh before commit" rule enforceable).
        stale_hash_design = repo / "stale-hash-design.md"
        stale_hash_design.write_text(
            "# Design: Stale\n- **Mode:** Legacy\n- **Basis Hash:** `deadbeefdeadbeef`\n"
            + norm_design.read_text(encoding="utf-8").split("\n", 1)[1],
            encoding="utf-8",
        )
        stale_res = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "check-design.py"), str(stale_hash_design)],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        assert stale_res.returncode == 1 and "stale" in stale_res.stdout, stale_res.stdout

        # 9.3 verify-basis.py & gen-report.py in a real temp git repo
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "src/orders/payment_guard.py"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
        base_sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()

        # Stamp -> FRESH
        subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "verify-basis.py"), "stamp", "--repo", str(repo), "--design", str(good_design), "--cmd", "pytest"],
            check=True, capture_output=True,
        )
        fresh = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "verify-basis.py"), "check", "--repo", str(repo), "--design", str(good_design)],
            capture_output=True, text=True, check=False,
        )
        assert fresh.returncode == 0 and "FRESH" in fresh.stdout

        # Modify code + add out-of-scope + noise -> STALE + report flags
        (repo / "src" / "orders" / "payment_guard.py").write_text("def prevent_duplicate_charge(order_id): return True\n", encoding="utf-8")
        (repo / "src" / "orders" / "extra.py").write_text("x = 1\n", encoding="utf-8")
        (repo / ".DS_Store").write_text("noise", encoding="utf-8")
        stale = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "verify-basis.py"), "check", "--repo", str(repo), "--design", str(good_design)],
            capture_output=True, text=True, check=False,
        )
        assert stale.returncode == 2 and "STALE" in stale.stdout

        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "feat: guard"], check=True)
        subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "verify-basis.py"), "stamp", "--repo", str(repo), "--design", str(good_design), "--cmd", "pytest"],
            check=True, capture_output=True,
        )
        rep = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "gen-report.py"), "--repo", str(repo), "--base", base_sha, "--head", "HEAD", "--design", str(good_design), "--depth", "D2 / R2", "--json"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        rep_data = json.loads(rep.stdout)
        assert ".DS_Store" in rep_data["noise_excluded"]
        assert "src/orders/extra.py" in rep_data["out_of_scope"]
        assert rep_data["verify_status"] == "FRESH"
    for rel, gate_tag in [
        ("skills/dev-workflow/SKILL.md", "[Recon Gate]"),
        ("skills/brainstorming/SKILL.md", "[Recon Gate]"),
        ("skills/save-design/SKILL.md", "[Design Gate]"),
        ("skills/legacy-impl/SKILL.md", "[Verify Stamp]"),
        ("skills/deep-review/SKILL.md", "[Verify Check]"),
        ("skills/deep-review/SKILL.md", "[Report Gate]"),
    ]:
        assert gate_tag in (PLUGIN_ROOT / rel).read_text(encoding="utf-8"), f"Missing {gate_tag} in {rel}"
    print("OK: dsh-dev-hub fusion scripts (repo-recon, check-design, verify-basis, gen-report) passed")


def main() -> int:
    check_json_files()
    check_skills_frontmatter()
    check_no_external_namespace()
    check_patches()
    check_hooks()
    check_pi_extension()
    check_codex_adaptation()
    check_plan_b_evolution()
    check_dsh_fusion_tools()
    print("=== ALL STANDALONE CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
