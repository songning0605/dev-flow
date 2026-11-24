#!/usr/bin/env python3
"""Verification basis-hash staleness guard for dev-workflow.

Inspired by dsh-dev-hub's verification.mjs:
- Computes a deterministic fingerprint over (design_basis_hash + git HEAD + working-tree diff + untracked files).
- `stamp`: records the verified fingerprint to `.git/dev-workflow-verify.json` (never pollutes tracked files).
- `check`: compares current state against the last stamp and reports FRESH (exit 0) or STALE (exit 2).

Usage:
  python3 scripts/verify-basis.py stamp --repo . --design docs/designs/foo.md --cmd "pytest"
  python3 scripts/verify-basis.py check --repo . --design docs/designs/foo.md
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

SCRIPT_DIR = Path(__file__).resolve().parent

_NOISE_FILTER = None


def is_noise_path(rel: str) -> bool:
    """Reuse gen-report.py's single noise definition (.DS_Store, dist/, node_modules/, ...)."""
    global _NOISE_FILTER
    if _NOISE_FILTER is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen_report", SCRIPT_DIR / "gen-report.py")
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _NOISE_FILTER = mod.is_noise_path
    return bool(_NOISE_FILTER(rel))


def compute_design_hash(design_path: Optional[Path]) -> str:
    if design_path is None or not design_path.is_file():
        return "none"
    # Inline import of check-design.py without requiring module rename
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_design", SCRIPT_DIR / "check-design.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    res = mod.check_design_file(design_path)
    return str(res["design_basis_hash"])


def run_git(repo: Path, args: list) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    return proc.stdout if proc.returncode == 0 else ""


def compute_repo_fingerprint(repo: Path, design_path: Optional[Path]) -> Dict[str, str]:
    design_hash = compute_design_hash(design_path)
    head = run_git(repo, ["rev-parse", "HEAD"]).strip() or "no-git"
    diff_unstaged = run_git(repo, ["diff", "--no-ext-diff"])
    diff_staged = run_git(repo, ["diff", "--cached", "--no-ext-diff"])
    untracked = run_git(repo, ["ls-files", "--others", "--exclude-standard"])

    code_hasher = hashlib.sha256()
    code_hasher.update(head.encode("utf-8"))
    code_hasher.update(b"\0")
    code_hasher.update(diff_staged.encode("utf-8"))
    code_hasher.update(b"\0")
    code_hasher.update(diff_unstaged.encode("utf-8"))
    for rel in sorted(ln.strip() for ln in untracked.splitlines() if ln.strip()):
        if is_noise_path(rel):
            continue
        p = repo / rel
        if p.is_file() and p.stat().st_size <= 512 * 1024:
            code_hasher.update(b"\0FILE:")
            code_hasher.update(rel.encode("utf-8"))
            code_hasher.update(b"\0")
            code_hasher.update(p.read_bytes())

    code_hash = code_hasher.hexdigest()[:16]
    combined = hashlib.sha256(f"{design_hash}:{code_hash}".encode("utf-8")).hexdigest()[:16]
    return {
        "design_basis_hash": design_hash,
        "head": head,
        "code_hash": code_hash,
        "combined_hash": combined,
    }


def default_state_file(repo: Path) -> Path:
    git_dir = run_git(repo, ["rev-parse", "--git-dir"]).strip()
    if git_dir:
        gpath = Path(git_dir)
        if not gpath.is_absolute():
            gpath = (repo / gpath).resolve()
        return gpath / "dev-workflow-verify.json"
    return repo / ".dev-workflow-verify.tmp.json"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Verification basis-hash staleness guard")
    sub = parser.add_subparsers(dest="action", required=True)

    for name in ("stamp", "check"):
        p = sub.add_parser(name)
        p.add_argument("--repo", type=Path, default=Path("."))
        p.add_argument("--design", type=Path, default=None)
        p.add_argument("--state-file", type=Path, default=None)
        p.add_argument("--json", action="store_true", dest="as_json")
        if name == "stamp":
            p.add_argument("--cmd", type=str, default="", help="Verification command that passed")

    args = parser.parse_args()
    repo = args.repo.resolve()
    state_file = args.state_file.resolve() if args.state_file else default_state_file(repo)
    current = compute_repo_fingerprint(repo, args.design.resolve() if args.design else None)

    if args.action == "stamp":
        record = {
            **current,
            "cmd": args.cmd,
            "stamped_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.as_json:
            print(json.dumps({"status": "STAMPED", **record}, ensure_ascii=False, indent=2))
        else:
            print(f"[verify-basis] STAMPED | combined={current['combined_hash']} | design={current['design_basis_hash']} | code={current['code_hash']}")
        return 0

    # check
    if not state_file.is_file():
        out = {"status": "STALE", "reason": "no_stamp", "current": current}
        print(json.dumps(out, ensure_ascii=False, indent=2) if args.as_json else "[verify-basis] STALE | reason=no_stamp")
        return 2

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    reasons = []
    if saved.get("design_basis_hash") != current["design_basis_hash"]:
        reasons.append("design_changed")
    if saved.get("code_hash") != current["code_hash"]:
        reasons.append("code_changed")

    if not reasons:
        out = {"status": "FRESH", "combined_hash": current["combined_hash"], "stamped_at": saved.get("stamped_at"), "cmd": saved.get("cmd", "")}
        print(json.dumps(out, ensure_ascii=False, indent=2) if args.as_json else f"[verify-basis] FRESH | combined={current['combined_hash']} | cmd={saved.get('cmd', '')}")
        return 0

    out = {"status": "STALE", "reasons": reasons, "saved": saved, "current": current}
    print(json.dumps(out, ensure_ascii=False, indent=2) if args.as_json else f"[verify-basis] STALE | reasons={','.join(reasons)}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
