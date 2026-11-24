#!/usr/bin/env python3
"""Design Document quality gate & basis-hash generator for dev-workflow.

Inspired by dsh-dev-hub's requirement.mjs (isRawEcho / missingForStart) and verification.mjs:
- Validates mandatory sections and rejects leftover placeholders (..., TBD, TODO).
- Enforces Legacy Mode guardrails (Current State & Seam, Scope Lock, Rollback, Non-Goals).
- Detects verbatim raw-prompt echo in Intent & Why (is_raw_echo).
- Computes a deterministic 16-char SHA-256 `design_basis_hash` over Goals, Non-Goals,
  Scope Lock files, Interfaces, and Verification strategy for staleness detection.

Usage:
  python3 scripts/check-design.py docs/designs/foo-design.md [--raw "原始一句话"] [--mode legacy|greenfield] [--json]
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PLACEHOLDER_PATTERNS = [
    re.compile(r"^\s*[-*]?\s*(\*\*[^*]+\*\*\s*)?(\.\.\.|…|TBD|TODO|待补充|（未填写）|（待确认）)\s*$", re.I),
    re.compile(r"<(Topic|relative-path-to-design-doc-or-url|filename|kebab-case-topic)>", re.I),
]

SQUASH_RE = re.compile(r"[\s，。！？；、,.!?;:：\"'“”‘’（）()\[\]【】<>《》\-—_~·`]+")
BACKTICK_PATH_RE = re.compile(r"`([^`\n]+)`")
LINE_SUFFIX_RE = re.compile(r":\d+(?:-\d+)?$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
UNFILLED_BASIS_HASH = "<populated by check-design.py>"


def normalize_scope_path(raw: str) -> str:
    """Normalize a Scope Lock path so it compares equal to `git diff` output.

    Handles Windows separators, leading `./`, and line-range suffixes
    (`src/orders/foo.py:120-145`) that designers add for precision.
    """
    raw_val = (raw or "").strip()
    root_relative = raw_val.startswith(".") or raw_val.startswith("\\")
    val = raw_val.replace("\\", "/")
    while val.startswith("./"):
        val = val[2:]
    if root_relative and val.startswith("/"):
        val = val[1:]
    return LINE_SUFFIX_RE.sub("", val)


def squash_text(value: str) -> str:
    return SQUASH_RE.sub("", (value or "").lower())


def is_raw_echo(value: str, raw: str) -> bool:
    a = squash_text(value)
    b = squash_text(raw)
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_s = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 12 and (short in long_s) and (len(short) / len(long_s) >= 0.8)


def parse_sections(markdown: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    current_key: Optional[str] = None
    buf: List[str] = []
    for line in markdown.replace("\r\n", "\n").splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current_key is not None:
                sections[current_key] = "\n".join(buf).strip()
            current_key = m.group(1).strip()
            buf = []
        elif current_key is not None:
            buf.append(line)
    if current_key is not None:
        sections[current_key] = "\n".join(buf).strip()
    return sections


SECTION_ALIASES: Dict[str, Tuple[str, ...]] = {
    "intent": ("intent", "意图", "动机"),
    "goals": ("goals", "目标"),
    "approaches": ("approaches", "方案"),
    "detailed design": ("detailed design", "详细设计"),
    "verification": ("verification", "验证"),
    "current state": ("current state", "现状"),
    "blast radius": ("blast radius", "影响面", "影响范围"),
}


def find_section(sections: Dict[str, str], keyword: str) -> Tuple[Optional[str], str]:
    aliases = SECTION_ALIASES.get(keyword.lower(), (keyword.lower(),))
    for heading, body in sections.items():
        lowered = heading.lower()
        if any(alias in lowered for alias in aliases):
            return heading, body
    return None, ""


def detect_mode_from_doc(markdown: str) -> str:
    m = re.search(r"\*\*Mode:\*\*\s*(Legacy|Greenfield)", markdown, re.I)
    return m.group(1).lower() if m else "legacy"


def extract_scope_files(design_section_body: str) -> List[str]:
    files: List[str] = []
    in_scope_block = False
    for line in design_section_body.splitlines():
        if re.search(r"Files to (Create|Modify)|文件改动|文件变更|文件修改|范围锁定|Scope Lock", line, re.I):
            in_scope_block = True
            for match in BACKTICK_PATH_RE.findall(line):
                raw = match.strip()
                if raw and raw != "..." and ("/" in raw or "." in raw):
                    files.append(normalize_scope_path(raw))
            continue
        if in_scope_block:
            if re.match(r"^\s*-\s+\*\*", line) and not re.search(r"Files to (Create|Modify)|文件改动|文件变更|文件修改|范围锁定|Scope Lock", line, re.I):
                in_scope_block = False
                continue
            for match in BACKTICK_PATH_RE.findall(line):
                raw = match.strip()
                if raw and raw != "..." and ("/" in raw or "." in raw):
                    files.append(normalize_scope_path(raw))
    seen = set()
    ordered = []
    for f in files:
        if f not in seen:
            seen.add(f)
            ordered.append(f)
    return ordered


def has_placeholder_only(body: str) -> bool:
    meaningful = [ln.strip() for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("| :---")]
    if not meaningful:
        return True
    return all(any(p.search(ln) for p in PLACEHOLDER_PATTERNS) for ln in meaningful)


def compute_design_basis_hash(sections: Dict[str, str], scope_files: List[str]) -> str:
    parts = [
        find_section(sections, "intent")[1],
        find_section(sections, "goals")[1],
        find_section(sections, "detailed design")[1],
        find_section(sections, "verification")[1],
        "\n".join(sorted(scope_files)),
    ]
    payload = "\n---\n".join(p.strip() for p in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def check_design_file(path: Path, raw_request: str = "", mode_override: Optional[str] = None) -> Dict[str, object]:
    text = path.read_text(encoding="utf-8")
    mode = (mode_override or detect_mode_from_doc(text)).lower()
    sections = parse_sections(text)

    errors: List[str] = []
    warnings: List[str] = []

    required_always = [
        ("intent", "Section 1: Intent & Why"),
        ("goals", "Section 2: Goals, Non-Goals & Anti-Goals"),
        ("approaches", "Section 4: Approaches Considered"),
        ("detailed design", "Section 5: Detailed Design & Interfaces"),
        ("verification", "Section 7: Verification & Test Strategy"),
    ]
    required_legacy = [
        ("current state", "Section 3: Current State & Isolation Seam"),
        ("blast radius", "Section 6: Blast Radius, Compatibility & Rollback"),
    ]

    for kw, label in required_always + (required_legacy if mode == "legacy" else []):
        heading, body = find_section(sections, kw)
        if not heading:
            errors.append(f"Missing required section: {label}")
        elif has_placeholder_only(body):
            errors.append(f"Section contains only placeholders or is empty: {heading}")

    # Check raw echo on Intent & Why
    _, intent_body = find_section(sections, "intent")
    if raw_request and intent_body and is_raw_echo(intent_body, raw_request):
        errors.append("Intent & Why is a verbatim echo of the raw user prompt; distill the root problem and why.")

    # Check Non-Goals and Rollback specifics in legacy mode
    _, goals_body = find_section(sections, "goals")
    if goals_body and not re.search(r"non-goals|非目标", goals_body, re.I):
        warnings.append("Goals section should explicitly declare Non-Goals.")

    _, rollback_body = find_section(sections, "blast radius")
    if mode == "legacy" and rollback_body and not re.search(r"rollback|回滚", rollback_body, re.I):
        errors.append("Legacy Mode requires an explicit Rollback Strategy.")

    # Check placeholder tokens anywhere in the file, skipping fenced code blocks
    # (design docs legitimately quote `...` / `TODO` inside code examples).
    fence_marker: Optional[str] = None
    fence_line = 0
    for idx, ln in enumerate(text.splitlines(), start=1):
        fence = FENCE_RE.match(ln)
        if fence:
            marker = fence.group(1)
            if fence_marker is None:
                fence_marker, fence_line = marker, idx
            elif marker[0] == fence_marker[0] and len(marker) >= len(fence_marker):
                fence_marker = None
            continue
        if fence_marker is not None:
            continue
        if UNFILLED_BASIS_HASH in ln:
            errors.append(
                f"Line {idx}: Basis Hash was never populated by check-design.py; "
                "write the computed hash into the header."
            )
        elif any(p.search(ln) for p in PLACEHOLDER_PATTERNS):
            warnings.append(f"Line {idx} looks like an unfilled placeholder: {ln.strip()[:80]}")
    if fence_marker is not None:
        warnings.append(
            f"Unclosed code fence opened at line {fence_line}; "
            "placeholder scan was truncated after it."
        )

    _, design_body = find_section(sections, "detailed design")
    scope_files = extract_scope_files(design_body)
    if mode == "legacy" and not scope_files:
        warnings.append("No concrete file paths found under 'Files to Create / Files to Modify (Scope Lock)' (范围锁定).")

    basis_hash = compute_design_basis_hash(sections, scope_files)

    # The header hash must match the body, otherwise a refined design keeps a stale stamp.
    header = re.search(r"\*\*Basis Hash:\*\*\s*`?([^`\n]*)`?", text)
    if header:
        header_hash = header.group(1).strip()
        if not header_hash:
            errors.append("Basis Hash header is empty; write the hash printed by check-design.py.")
        elif header_hash != UNFILLED_BASIS_HASH and header_hash != basis_hash:
            errors.append(
                f"Header Basis Hash `{header_hash}` is stale: the design body currently hashes to `{basis_hash}`."
            )

    return {
        "ok": len(errors) == 0,
        "path": str(path),
        "mode": mode,
        "design_basis_hash": basis_hash,
        "scope_files": scope_files,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Validate a dev-workflow Design Doc and compute design_basis_hash")
    parser.add_argument("design_path", type=Path, help="Path to design markdown file")
    parser.add_argument("--raw", type=str, default="", help="Original user request (for raw-echo detection)")
    parser.add_argument("--mode", choices=["legacy", "greenfield"], default=None, help="Override detected mode")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON output")
    args = parser.parse_args()

    if not args.design_path.is_file():
        print(f"ERROR: design file not found: {args.design_path}", file=sys.stderr)
        return 1

    res = check_design_file(args.design_path, raw_request=args.raw, mode_override=args.mode)
    if args.as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if res["ok"] else "FAIL"
        print(f"[check-design] {status} | mode={res['mode']} | design_basis_hash={res['design_basis_hash']} | scope_files={len(res['scope_files'])}")
        for err in res["errors"]:
            print(f"  ERROR: {err}")
        for warn in res["warnings"]:
            print(f"  WARN: {warn}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
