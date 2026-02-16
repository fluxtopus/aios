#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from _common import component_matches_file, dump_json, load_yaml


def git_changed_files(base: str, head: str) -> list[str]:
    cmd = ["git", "diff", "--name-only", base, head]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect changed components from git diff")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    config = load_yaml(repo_root / args.config)

    changed_files = git_changed_files(args.base, args.head)

    changed_components: set[str] = set()
    component_files: dict[str, list[str]] = {}

    for rel_file in changed_files:
        for component in config["components"]:
            if component_matches_file(component, rel_file):
                name = component["name"]
                changed_components.add(name)
                component_files.setdefault(name, []).append(rel_file)

    output = {
        "base": args.base,
        "head": args.head,
        "files": changed_files,
        "components": sorted(changed_components),
        "component_files": {k: sorted(v) for k, v in sorted(component_files.items())},
    }

    dump_json(Path(args.output), output)
    print(f"Detected {len(output['components'])} changed component(s)")


if __name__ == "__main__":
    main()
