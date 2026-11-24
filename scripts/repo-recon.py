#!/usr/bin/env python3
"""Deterministic local repository fast recon + 4-class intent classifier for dev-workflow.

Inspired by dsh-dev-hub's recon.mjs and intent.mjs:
- Zero LLM calls, zero external dependencies, pure Python 3 stdlib.
- Extracts English identifiers + Chinese phrases/2-grams with stop-word filtering.
- Computes IDF-weighted file relevance scores and exact matching line snippets.
- Classifies user intent into: bug | feature | refactor | analysis.

Usage:
  python3 scripts/repo-recon.py --repo . --query "修复订单状态机重复扣款" [--max-files 15] [--json]
"""

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

SKIP_DIRS: Set[str] = {
    "node_modules", ".git", "target", "build", "dist", "out", "coverage", ".next",
    "vendor", ".idea", ".vscode", ".gradle", "__pycache__", ".venv", "venv", ".dev-hub",
}

TEXT_EXTS: Set[str] = {
    ".java", ".kt", ".kts", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro",
    ".css", ".scss", ".sass", ".less", ".html", ".py", ".go", ".rs", ".rb", ".php", ".cs", ".cpp", ".c", ".h",
    ".xml", ".yml", ".yaml", ".json", ".md", ".sql", ".sh", ".properties", ".gradle", ".toml", ".txt",
}

CJK_STOP_CHARS = re.compile(r"[的了着过给和与把被为对从到向在就也都很更最会能可要将需想使让并且但而且或是之其这那个上下中里后前时]")
CJK_STOP_WORDS: Set[str] = {
    "实现", "支持", "新增", "修改", "需要", "可以", "功能", "进行", "完成", "处理", "使用",
    "以及", "相关", "内容", "问题", "代码", "文件", "方法", "时候", "一个", "这个", "什么",
    "怎么", "如何", "现在", "目前", "希望", "能够", "应该", "不要", "没有", "已有", "补齐",
}
EN_STOP_WORDS: Set[str] = {
    "the", "and", "for", "with", "that", "this", "from", "into", "when", "then", "than", "have", "has",
    "are", "was", "were", "will", "would", "should", "could", "not", "but", "you", "your", "our", "its",
    "of", "to", "in", "on", "at", "by", "as", "is", "be", "or", "an", "it", "we", "can", "need", "want",
    "add", "new", "use", "make", "let", "get", "set",
}

BUG_WORDS = [
    "bug", "fix", "error", "crash", "fail", "regression", "timeout", "500", "404",
    "修复", "报错", "异常", "崩溃", "失败", "不生效", "不工作", "回归", "排查", "定位", "错误", "超时", "卡住", "错乱", "不一致", "重复",
]
REFACTOR_WORDS = [
    "refactor", "rewrite", "decouple", "extract", "rename", "cleanup", "simplify", "modularize",
    "重构", "重写", "拆分", "解耦", "提取", "抽取", "重命名", "整理代码", "清理代码", "替换实现", "模块化", "去重", "简化",
]
FEATURE_WORDS = [
    "feature", "implement", "support", "integrate", "migrate", "extend",
    "新增", "支持", "需求", "功能", "实现", "加一个", "增加", "接入", "改造", "优化", "迁移", "扩展",
]
ANALYSIS_WORDS = [
    "analyze", "audit", "investigate", "explain", "trace", "read-only",
    "分析", "梳理", "盘点", "调研", "评估", "诊断", "解释", "说明一下", "看看", "为什么", "调用链", "只读",
]

IMPORT_LINE_RE = re.compile(r"^\s*(package|import|from\s+\S+\s+import)\b")
BUILD_ARTIFACT_RE = re.compile(r"(^|/)(lib|dist|build|out|target|coverage)/|\.min\.js$", re.I)
CODE_PATH_RE = re.compile(r"\.(java|kt|ts|tsx|js|jsx|mjs|vue|py|go|rs|rb|php|cs|cpp|c)$", re.I)


def detect_intent(description: str, fallback: str = "feature") -> str:
    text = (description or "").strip().lower()
    if not text:
        return fallback
    bug_score = sum(1 for w in BUG_WORDS if w in text)
    refactor_score = sum(1 for w in REFACTOR_WORDS if w in text)
    feature_score = sum(1 for w in FEATURE_WORDS if w in text)
    if bug_score > 0 and bug_score >= refactor_score:
        return "bug"
    if refactor_score > 0 and refactor_score >= feature_score:
        return "refactor"
    if feature_score > 0:
        return "feature"
    analysis_score = sum(1 for w in ANALYSIS_WORDS if w in text)
    return "analysis" if analysis_score > 0 else fallback


def extract_tokens(description: str, max_tokens: int = 30) -> List[str]:
    text = description or ""
    ascii_tokens = [
        w for w in re.findall(r"[a-z][a-z0-9_-]{2,}", text.lower())
        if w not in EN_STOP_WORDS
    ]
    cjk_runs = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    cjk_tokens: List[str] = []
    for run in cjk_runs:
        cjk_tokens.append(run)
        if len(run) > 4:
            for i in range(0, len(run) - 1):
                bg = run[i : i + 2]
                if CJK_STOP_CHARS.search(bg) or bg in CJK_STOP_WORDS:
                    continue
                cjk_tokens.append(bg)
    seen: Set[str] = set()
    out: List[str] = []
    for tok in ascii_tokens + cjk_tokens:
        val = tok.strip()
        if len(val) < 2 or val in seen:
            continue
        if val in CJK_STOP_WORDS:
            continue
        if len(val) == 2 and CJK_STOP_CHARS.search(val):
            continue
        seen.add(val)
        out.append(val)
        if len(out) >= max_tokens:
            break
    return out


def is_cjk(token: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", token))


def walk_text_files(repo: Path, max_scan: int = 4000, max_depth: int = 12, max_bytes: int = 256 * 1024) -> Tuple[List[Path], bool]:
    out: List[Path] = []
    truncated = False

    def visit(directory: Path, depth: int) -> None:
        nonlocal truncated
        if depth > max_depth or len(out) >= max_scan or truncated:
            return
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name)
        except OSError:
            return
        for entry in entries:
            if len(out) >= max_scan:
                truncated = True
                return
            if entry.name.startswith(".") and entry.name != ".github":
                continue
            if entry.is_dir(follow_symlinks=False):
                if entry.name in SKIP_DIRS:
                    continue
                visit(Path(entry.path), depth + 1)
                continue
            if not entry.is_file(follow_symlinks=False):
                continue
            ext = Path(entry.name).suffix.lower()
            if ext not in TEXT_EXTS:
                continue
            try:
                if entry.stat(follow_symlinks=False).st_size > max_bytes:
                    continue
            except OSError:
                continue
            out.append(Path(entry.path))

    visit(repo, 0)
    return out, truncated


def match_lines(content: str, tokens: List[str], limit: int) -> List[Dict[str, object]]:
    preferred: List[Dict[str, object]] = []
    fallback: List[Dict[str, object]] = []
    for idx, raw_line in enumerate(content.splitlines(), start=1):
        lower = raw_line.lower()
        if not any(tok in lower for tok in tokens):
            continue
        text = raw_line.strip()
        if not text:
            continue
        if len(text) > 180:
            text = text[:180] + "…"
        entry = {"line": idx, "text": text}
        if IMPORT_LINE_RE.match(text):
            fallback.append(entry)
        else:
            preferred.append(entry)
        if len(preferred) >= limit:
            break
    return (preferred + fallback)[:limit]


def pick_narrow_scope(files: List[Dict[str, object]], max_dirs: int = 4) -> List[str]:
    chosen: List[str] = []
    for item in files[:10]:
        rel = str(item["path"])
        parent = rel.rsplit("/", 1)[0] if "/" in rel else rel
        if not parent or parent in chosen:
            continue
        if any(existing.startswith(parent + "/") for existing in chosen):
            continue
        chosen = [existing for existing in chosen if not parent.startswith(existing + "/")]
        chosen.append(parent)
        if len(chosen) >= max_dirs:
            break
    return chosen


def detect_workspace(repo: Path) -> List[str]:
    """Return immediate sub-directories that are independent git repos (multi-repo workspace)."""
    repos: List[str] = []
    try:
        entries = sorted(os.scandir(repo), key=lambda e: e.name)
    except OSError:
        return repos
    for entry in entries:
        if entry.name.startswith(".") or not entry.is_dir(follow_symlinks=False):
            continue
        if (Path(entry.path) / ".git").exists():
            repos.append(entry.name)
    return repos


def recon_repo(repo: Path, query: str, max_files: int = 15, max_matches_per_file: int = 3) -> Dict[str, object]:
    intent = detect_intent(query)
    tokens = extract_tokens(query)
    result: Dict[str, object] = {
        "repo": str(repo.resolve()),
        "query": query.strip(),
        "intent": intent,
        "tokens": tokens,
        "effective_tokens": [],
        "scanned": 0,
        "truncated": False,
        "workspace_repos": detect_workspace(repo),
        "suggested_scope": [],
        "files": [],
    }
    if not tokens:
        return result

    candidates, truncated = walk_text_files(repo)
    result["scanned"] = len(candidates)
    result["truncated"] = truncated
    if not candidates:
        return result

    per_file = []
    df: Dict[str, int] = {}
    for path in candidates:
        rel = path.relative_to(repo).as_posix()
        lower_rel = rel.lower()
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            content = ""
        matches = match_lines(content, tokens, max(12, max_matches_per_file)) if content else []
        lower_matches = [str(m["text"]).lower() for m in matches]
        hit_tokens = {
            tok for tok in tokens
            if (tok in lower_rel) or any(tok in text for text in lower_matches)
        }
        for tok in hit_tokens:
            df[tok] = df.get(tok, 0) + 1
        if hit_tokens:
            per_file.append((rel, lower_rel, matches))

    ubiquitous = max(3, int(len(candidates) * 0.15))
    kept = [
        tok for tok in tokens
        if df.get(tok, 0) > 0 and (not is_cjk(tok) or df[tok] <= ubiquitous)
    ]
    if not kept:
        kept = [tok for tok in tokens if df.get(tok, 0) > 0]

    scored = []
    rare_cutoff = max(5, int(len(candidates) * 0.02))
    specific = [tok for tok in kept if (is_cjk(tok) or df.get(tok, 0) <= rare_cutoff)]
    pick_tokens = specific or kept

    for rel, lower_rel, matches in per_file:
        score = 0.0
        base = lower_rel.rsplit("/", 1)[-1]
        lower_matches = [str(m["text"]).lower() for m in matches]
        for tok in kept:
            weight = 1.0 + math.log((len(candidates) + 1) / (df.get(tok, 1) + 1))
            if tok in base:
                score += 7.0 * weight
            elif tok in lower_rel:
                score += 4.0 * weight
            if any(tok in text for text in lower_matches):
                score += weight
        if score <= 0:
            continue
        if BUILD_ARTIFACT_RE.search(lower_rel):
            score *= 0.4
        filtered_matches = [m for m in matches if any(tok in str(m["text"]).lower() for tok in pick_tokens)] or matches
        meaningful = [m for m in filtered_matches if not IMPORT_LINE_RE.match(str(m["text"]))] or filtered_matches
        is_code = bool(CODE_PATH_RE.search(rel)) and "/test/" not in f"/{rel}" and not rel.startswith("docs/")
        scored.append({
            "path": rel,
            "score": round(score, 1),
            "is_code": is_code,
            "matches": meaningful[:max_matches_per_file],
        })

    scored.sort(key=lambda x: (-x["score"], -int(x["is_code"]), x["path"]))
    trimmed = [
        {"path": item["path"], "score": item["score"], "matches": item["matches"]}
        for item in scored[:max_files]
    ]
    result["effective_tokens"] = kept
    result["files"] = trimmed
    result["suggested_scope"] = pick_narrow_scope(trimmed)
    return result


def format_markdown(res: Dict[str, object]) -> str:
    lines = [
        f"Intent: {res['intent']} | Scanned: {res['scanned']} files | Suggested Scope: {', '.join(res['suggested_scope']) or '(none)'}",
        f"Effective Tokens: {', '.join(res['effective_tokens']) or '(none)'}",
    ]
    if res.get("truncated"):
        lines.append("TRUNCATED: scan hit the built-in 4000-file cap — treat this receipt as a partial sample.")
    workspace_repos = res.get("workspace_repos") or []
    if workspace_repos:
        shown = ", ".join(workspace_repos[:8]) + (" …" if len(workspace_repos) > 8 else "")
        lines.append(
            f"WORKSPACE: {len(workspace_repos)} independent git repos detected ({shown}); "
            "rerun with --repo <repo> for an accurate scope."
        )
    files = res["files"]
    if not files:
        lines.append("Candidate Files: (none matched)")
    else:
        lines.append("Candidate Files:")
        for f in files:
            lines.append(f"  - {f['path']} (score={f['score']})")
            for m in f["matches"]:
                lines.append(f"      L{m['line']}: {m['text']}")
    return "\n".join(lines)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Deterministic local repository fast recon + intent classifier")
    parser.add_argument("--repo", type=Path, default=Path("."), help="Repository root directory")
    parser.add_argument("--query", type=str, required=True, help="User task description")
    parser.add_argument("--max-files", type=int, default=15, help="Maximum candidate files to return")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON output")
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"ERROR: repo directory not found: {repo}", file=sys.stderr)
        return 1

    res = recon_repo(repo, args.query, max_files=max(1, min(args.max_files, 50)))
    if args.as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
