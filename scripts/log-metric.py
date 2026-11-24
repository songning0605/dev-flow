#!/usr/bin/env python3
"""Lightweight, bounded, schema-enforced metrics logger for dev-workflow Plan B evolution.

Guarantees:
- Stored outside business repos (~/.agent-plugins/dev-workflow-metrics.jsonl by default)
- Strict whitelist schema (no code, diffs, paths, or raw prompts)
- Hard 500-byte cap per JSON line
- Rolling-window reads (--tail 30) and archive rotation (--rotate --keep 10)
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import List

DEFAULT_LOG = Path.home() / ".agent-plugins" / "dev-workflow-metrics.jsonl"
MAX_LINE_BYTES = 500
VALID_MODES = {"legacy", "greenfield"}
VALID_D = {"D0", "D1", "D2", "D3"}
VALID_R = {"R0", "R1", "R2", "R3"}
VALID_ESCALATIONS = {"D_ESCALATED", "SCOPE_EXPANDED", "DESIGN_DEVIATION", "NO_CHAR_TEST"}
# Order = dispatch order in improving-design/perspectives.md (D1: 1-2, D2: 1-3, D3: 1-5)
PERSPECTIVE_ORDER = ("free-form", "legacy-compat", "minimal-diff", "testability", "yagni")
VALID_PERSPECTIVES = set(PERSPECTIVE_ORDER)
D_PERSPECTIVE_LIMIT = {"D0": 0, "D1": 2, "D2": 3, "D3": len(PERSPECTIVE_ORDER)}
D_ORDER = ("D0", "D1", "D2", "D3")
R_ORDER = ("R0", "R1", "R2", "R3")
R_ESCALATION_FLAGS = {"SCOPE_EXPANDED", "DESIGN_DEVIATION", "NO_CHAR_TEST"}


def check_cross_field_invariants(
    init_d: str, final_d: str, init_r: str, final_r: str,
    escalations: List[str], perspectives: List[str],
) -> None:
    """3 absolute invariants (no deeper cross-checking)."""
    if final_d == "D0" and perspectives:
        raise ValueError("final-d=D0 skips Improve Design, so hit-perspectives must be empty")
    allowed = PERSPECTIVE_ORDER[: D_PERSPECTIVE_LIMIT[final_d]]
    disallowed = [p for p in perspectives if p not in allowed]
    if disallowed:
        raise ValueError(
            f"hit-perspectives {disallowed} are not dispatched at final-d={final_d} "
            f"(allowed: {', '.join(allowed) or 'none'})"
        )
    if "D_ESCALATED" in escalations and D_ORDER.index(final_d) <= D_ORDER.index(init_d):
        raise ValueError(f"D_ESCALATED requires final-d > init-d, got {init_d} -> {final_d}")
    r_flags = R_ESCALATION_FLAGS & set(escalations)
    if r_flags and R_ORDER.index(final_r) < R_ORDER.index(init_r):
        raise ValueError(
            f"review escalation {sorted(r_flags)} requires final-r >= init-r, got {init_r} -> {final_r}"
        )


def append_entry(log_path: Path, args: argparse.Namespace) -> None:
    if args.repo_mode not in VALID_MODES:
        raise ValueError(f"Invalid repo-mode: {args.repo_mode}")
    for name, val, allowed in [
        ("init-d", args.init_d, VALID_D),
        ("final-d", args.final_d, VALID_D),
        ("init-r", args.init_r, VALID_R),
        ("final-r", args.final_r, VALID_R),
    ]:
        if val not in allowed:
            raise ValueError(f"Invalid {name}: {val}")

    escalations = [x for x in (args.escalations.split(",") if args.escalations else []) if x]
    for e in escalations:
        if e not in VALID_ESCALATIONS:
            raise ValueError(f"Invalid escalation flag: {e}")

    perspectives = [x for x in (args.hit_perspectives.split(",") if args.hit_perspectives else []) if x]
    for p in perspectives:
        if p not in VALID_PERSPECTIVES:
            raise ValueError(f"Invalid perspective id: {p}")

    check_cross_field_invariants(args.init_d, args.final_d, args.init_r, args.final_r, escalations, perspectives)

    tags = [t.strip()[:32] for t in (args.friction_tags.split(",") if args.friction_tags else []) if t.strip()][:3]

    entry = {
        "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": args.repo_mode,
        "init_d": args.init_d,
        "final_d": args.final_d,
        "init_r": args.init_r,
        "final_r": args.final_r,
        "escalations": escalations,
        "hit_perspectives": perspectives,
        "missed_by_design": bool(args.missed_by_design),
        "ruling_count": max(0, int(args.ruling_count)),
        "friction_tags": tags,
    }
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
    if len(line.encode("utf-8")) > MAX_LINE_BYTES:
        raise ValueError(f"Metric line exceeds {MAX_LINE_BYTES} bytes")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")
    print(f"Logged metric to {log_path} ({len(line.encode('utf-8'))} bytes)")


def tail_entries(log_path: Path, n: int) -> None:
    if not log_path.is_file():
        print("[]")
        return
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    recent = [json.loads(ln) for ln in lines[-max(1, n):]]
    print(json.dumps(recent, ensure_ascii=False, indent=2))


def rotate_log(log_path: Path, keep: int) -> None:
    if not log_path.is_file():
        print("No active metrics file to rotate.")
        return
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) <= keep:
        print(f"Active log has {len(lines)} lines (<= keep={keep}); nothing archived.")
        return
    to_archive = lines[:-keep] if keep > 0 else lines
    to_keep = lines[-keep:] if keep > 0 else []
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m")
    archive_path = log_path.with_name(f"{log_path.stem}-archive-{stamp}.jsonl")
    with archive_path.open("a", encoding="utf-8", newline="\n") as f:
        for ln in to_archive:
            f.write(ln + "\n")
    log_path.write_text("\n".join(to_keep) + ("\n" if to_keep else ""), encoding="utf-8")
    print(f"Archived {len(to_archive)} lines -> {archive_path}; kept {len(to_keep)} active lines.")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Bounded metrics logger for dev-workflow Plan B evolution")
    parser.add_argument("--file", type=Path, default=DEFAULT_LOG, help="Override metrics jsonl path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_log = sub.add_parser("log", help="Append one whitelisted metric line")
    p_log.add_argument("--repo-mode", required=True, choices=sorted(VALID_MODES))
    p_log.add_argument("--init-d", required=True)
    p_log.add_argument("--final-d", required=True)
    p_log.add_argument("--init-r", required=True)
    p_log.add_argument("--final-r", required=True)
    p_log.add_argument("--escalations", default="", help="Comma-separated escalation flags")
    p_log.add_argument("--hit-perspectives", default="", help="Comma-separated perspective IDs")
    p_log.add_argument("--missed-by-design", action="store_true")
    p_log.add_argument("--ruling-count", type=int, default=0)
    p_log.add_argument("--friction-tags", default="", help="Up to 3 short tags (<=32 chars each)")

    p_tail = sub.add_parser("tail", help="Read last N metric entries as JSON array")
    p_tail.add_argument("-n", type=int, default=30)

    p_rot = sub.add_parser("rotate", help="Archive older entries and trim active file")
    p_rot.add_argument("--keep", type=int, default=10)

    args = parser.parse_args()
    if args.cmd == "log":
        append_entry(args.file, args)
    elif args.cmd == "tail":
        tail_entries(args.file, args.n)
    elif args.cmd == "rotate":
        rotate_log(args.file, args.keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
