#!/usr/bin/env python3
"""Sync vendored skills from obra/superpowers, rewrite namespaces, overlay custom skills, apply patches, and test.

Usage:
  # Sync from a local checkout of obra/superpowers (offline/local build):
  python3 scripts/sync-upstream.py --source /path/to/obra/superpowers

  # Sync directly from GitHub upstream main (requires git & network):
  python3 scripts/sync-upstream.py
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yml", ".yaml", ".sh", ".js", ".cjs", ".ts", ".html", ".dot"}


def rewrite_namespace_in_tree(root: Path, src_ns: str, dst_ns: str) -> int:
    changed = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS or path.parent.name == "scripts":
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if src_ns in content:
                path.write_text(content.replace(src_ns, dst_ns), encoding="utf-8")
                changed += 1
    return changed


def apply_patches(patches_file: Path) -> None:
    patches = json.loads(patches_file.read_text(encoding="utf-8"))
    for p in patches:
        target = PLUGIN_ROOT / p["file"]
        if not target.exists():
            raise RuntimeError(f"Patch '{p['id']}' failed: target file missing: {p['file']}")
        text = target.read_text(encoding="utf-8")
        if p["find"] not in text:
            raise RuntimeError(
                f"Patch '{p['id']}' failed: anchor text not found in {p['file']}.\n"
                f"Upstream likely changed this section. Update custom/patches/patches.json."
            )
        target.write_text(text.replace(p["find"], p["replace"], 1), encoding="utf-8")
        print(f"Applied patch: {p['id']} -> {p['file']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync obra/superpowers into standalone dev-workflow plugin")
    parser.add_argument("--source", type=Path, default=None, help="Local path to obra/superpowers checkout")
    parser.add_argument("--commit", type=str, default=None, help="Commit SHA to record in upstream.lock")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests/test-plugin.sh")
    args = parser.parse_args()

    manifest = json.loads((PLUGIN_ROOT / "vendor-manifest.json").read_text(encoding="utf-8"))
    lock_path = PLUGIN_ROOT / "upstream.lock"
    lock_data = json.loads(lock_path.read_text(encoding="utf-8"))

    temp_dir = None
    try:
        if args.source is not None:
            upstream_dir = args.source.resolve()
            resolved_commit = args.commit or lock_data.get("commit", "local")
        else:
            temp_dir = Path(tempfile.mkdtemp(prefix="superpowers-sync-"))
            repo_url = lock_data["repository"]
            branch = lock_data.get("branch", "main")
            print(f"Cloning {repo_url} ({branch})...")
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(temp_dir)],
                check=True,
            )
            resolved_commit = subprocess.check_output(
                ["git", "-C", str(temp_dir), "rev-parse", "HEAD"], text=True, encoding="utf-8"
            ).strip()
            upstream_dir = temp_dir

        skills_dir = PLUGIN_ROOT / "skills"
        if skills_dir.exists():
            shutil.rmtree(skills_dir)
        skills_dir.mkdir(parents=True, exist_ok=True)

        # 1. Copy vendored upstream skills
        for skill_name in manifest["vendored_skills"]:
            src = upstream_dir / "skills" / skill_name
            if not src.exists():
                raise RuntimeError(f"Expected upstream skill missing: {src}")
            shutil.copytree(src, skills_dir / skill_name)
            print(f"Vendored upstream skill: {skill_name}")

        # 2. Copy upstream LICENSE for MIT compliance
        upstream_license = upstream_dir / "LICENSE"
        if upstream_license.exists():
            shutil.copy2(upstream_license, PLUGIN_ROOT / "LICENSE")

        # 3. Rewrite namespace superpowers: -> dev-workflow:
        rewritten = rewrite_namespace_in_tree(
            skills_dir, manifest["source_namespace"], manifest["target_namespace"]
        )
        print(f"Rewrote namespace in {rewritten} vendored files.")

        # 4. Overlay custom skills (always win)
        custom_skills = PLUGIN_ROOT / "custom" / "skills"
        for item in sorted(custom_skills.iterdir()):
            if item.is_dir():
                dst = skills_dir / item.name
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(item, dst)
                print(f"Overlayed custom skill: {item.name}")

        # 5. Apply declarative patches to vendored skills
        apply_patches(PLUGIN_ROOT / "custom" / "patches" / "patches.json")

        # 6. Update upstream.lock
        lock_data["commit"] = resolved_commit
        lock_path.write_text(json.dumps(lock_data, indent=2) + "\n", encoding="utf-8")
        print(f"Updated upstream.lock -> {resolved_commit}")

        # 7. Run automated verification
        if not args.skip_tests:
            test_script = PLUGIN_ROOT / "tests" / "test_plugin.py"
            subprocess.run([sys.executable, str(test_script)], check=True)

        return 0
    finally:
        if temp_dir is not None and temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    sys.exit(main())
