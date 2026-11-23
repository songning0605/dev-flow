#!/usr/bin/env python3
"""Noise-filtered delivery report & Scope-Lock auditor for dev-workflow.

Inspired by dsh-dev-hub's report.mjs:
- Reads `git diff --name-status <base>..<head>` (or working tree vs base).
- Automatically excludes OS/IDE/build noise (.DS_Store, Thumbs.db, node_modules/, dist/, etc.)
  and explicitly lists excluded noise for audit transparency.
- Cross-checks changed files against the Design Doc's Scope Lock (`Files to Create/Modify`)
  and flags any out-of-scope edits.
- Checks verification basis freshness and emits a clean Markdown report ready for PR bodies.

Usage:
  python3 scripts/gen-report.py --repo . --base main --head HEAD [--design docs/designs/foo.md] [--depth "D2 / R2"] [--out report.md]
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent

NOISE_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", ".localized"}
NOISE_DIR_RE = re.compile(r"(^|/)(\.idea|\.vscode|node_modules|target|dist|build|__pycache__)/")

STATUS_MAP = {
    "A": "Added",
    "M": "Modified",
    "D": "Deleted",
    "R": "Renamed",
}


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def is_noise_path(rel: str) -> bool:
    norm = rel.replace("\\", "/")
    base = norm.rsplit("/", 1)[-1]
    return (base in NOISE_NAMES) or bool(NOISE_DIR_RE.search(norm))


def git_changed_files(repo: Path, base: str, head: str) -> Tuple[List[Dict[str, str]], bool]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-status", f"{base}..{head}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if proc.returncode != 0:
        return [], False
    out = []
    for ln in proc.stdout.splitlines():
        if not ln.strip():
            continue
        parts = ln.split("\t")
        code = parts[0][0]
        path = parts[-1].replace("\\", "/")
        out.append({"status": STATUS_MAP.get(code, parts[0]), "path": path})
    return out, True


def generate_report(
    repo: Path,
    base: str,
    head: str,
    design_path: Optional[Path] = None,
    depth: str = "N/A",
    escalations: str = "",
    state_file: Optional[Path] = None,
) -> Tuple[str, Dict[str, object]]:
    raw_files, git_ok = git_changed_files(repo, base, head)
    clean_files = [f for f in raw_files if not is_noise_path(f["path"])]
    noise_files = [f["path"] for f in raw_files if is_noise_path(f["path"])]

    scope_files: List[str] = []
    design_rel = ""
    design_basis = "none"
    if design_path and design_path.is_file():
        check_mod = load_module("check_design", "check-design.py")
        info = check_mod.check_design_file(design_path)
        scope_files = list(info["scope_files"])
        design_basis = str(info["design_basis_hash"])
        try:
            design_rel = design_path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            design_rel = str(design_path)

    out_of_scope: List[str] = []
    if scope_files:
        allowed = set(scope_files)
        if design_rel:
            allowed.add(design_rel)
        for f in clean_files:
            p = f["path"]
            if p not in allowed and not any(p.startswith(s.rstrip("/") + "/") for s in allowed if not Path(s).suffix):
                out_of_scope.append(p)

    # Check verification stamp freshness
    verify_mod = load_module("verify_basis", "verify-basis.py")
    sf = state_file.resolve() if state_file else verify_mod.default_state_file(repo.resolve())
    verify_status = "UNVERIFIED"
    verify_cmd = ""
    if sf.is_file():
        saved = json.loads(sf.read_text(encoding="utf-8"))
        cur = verify_mod.compute_repo_fingerprint(repo.resolve(), design_path.resolve() if design_path else None)
        verify_cmd = str(saved.get("cmd", ""))
        if saved.get("design_basis_hash") == cur["design_basis_hash"] and saved.get("code_hash") == cur["code_hash"]:
            verify_status = "FRESH"
        else:
            verify_status = "STALE"

    boundaries = []
    if not git_ok:
        boundaries.append("Git diff range could not be resolved; file list is incomplete.")
    if verify_status != "FRESH":
        boundaries.append(f"Verification stamp is {verify_status} (re-run tests and stamp before merging).")
    if out_of_scope:
        boundaries.append(f"{len(out_of_scope)} file(s) changed outside Design Doc Scope Lock.")
    if escalations.strip():
        boundaries.append(f"Escalation flags recorded: {escalations.strip()}.")
    if not boundaries:
        boundaries.append("All changed files are within Scope Lock and verification stamp is FRESH.")

    lines = [
        "## Design & Key Decisions",
        f"- **Design Doc:** `{design_rel or 'N/A'}` (Basis Hash: `{design_basis}`)",
        f"- **Workflow Depth:** `{depth}`",
        f"- **Verification Status:** `{verify_status}`" + (f" (`{verify_cmd}`)" if verify_cmd else ""),
        "",
        "## Changed Files & Scope Compliance",
    ]
    if clean_files:
        for f in clean_files:
            flag = " **[OUT-OF-SCOPE]**" if f["path"] in out_of_scope else ""
            lines.append(f"- `{f['status']}` `{f['path']}`{flag}")
    else:
        lines.append("- (no non-noise file changes detected)")

    if noise_files:
        lines.extend(["", "## Excluded Local Noise", *[f"- `{p}`" for p in noise_files]])

    lines.extend(["", "## Evidence Boundaries", *[f"- {b}" for b in boundaries]])

    meta = {
        "changed_count": len(clean_files),
        "noise_excluded": noise_files,
        "out_of_scope": out_of_scope,
        "verify_status": verify_status,
        "design_basis_hash": design_basis,
    }
    return "\n".join(lines) + "\n", meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate noise-filtered delivery report & Scope-Lock audit")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--base", type=str, required=True)
    parser.add_argument("--head", type=str, default="HEAD")
    parser.add_argument("--design", type=Path, default=None)
    parser.add_argument("--depth", type=str, default="N/A")
    parser.add_argument("--escalations", type=str, default="")
    parser.add_argument("--state-file", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    md, meta = generate_report(
        repo=args.repo.resolve(),
        base=args.base,
        head=args.head,
        design_path=args.design.resolve() if args.design else None,
        depth=args.depth,
        escalations=args.escalations,
        state_file=args.state_file,
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
    if args.as_json:
        print(json.dumps({**meta, "markdown": md}, ensure_ascii=False, indent=2))
    else:
        print(md, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
