#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _common import component_map, dump_json, load_json, load_yaml, read_component_version, write_component_version


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply version bumps from plan JSON")
    parser.add_argument("--config", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=False, help="Optional path for changed-files JSON")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    config = load_yaml(repo_root / args.config)
    plan = load_json(Path(args.plan))

    components_by_name = component_map(config)
    changed_files: dict[str, list[str]] = {}

    for item in plan.get("components", []):
        name = item["name"]
        component = components_by_name[name]

        expected_current = item["current_version"]
        current_now = read_component_version(repo_root, component)
        if current_now != expected_current:
            raise SystemExit(
                f"Version drift for {name}: expected {expected_current}, found {current_now}."
            )

        new_version = item["next_version"]
        changed = write_component_version(repo_root, component, new_version)
        changed_files[name] = changed
        print(f"Bumped {name}: {expected_current} -> {new_version}")

    if args.output:
        dump_json(Path(args.output), {"changed_files": changed_files})


if __name__ == "__main__":
    main()
