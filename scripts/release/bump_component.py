#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from _common import (
    bump_semver,
    component_map,
    dump_json,
    ensure_valid_bump,
    load_yaml,
    read_component_version,
    resolve_component_name,
    write_component_version,
)


def run_update_manifest(config_path: str, manifest_path: str) -> None:
    update_manifest_script = Path(__file__).with_name("update_manifest.py")
    subprocess.run(
        [
            "python3",
            str(update_manifest_script),
            "--config",
            config_path,
            "--output",
            manifest_path,
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump one component version safely")
    parser.add_argument("--config", required=True)
    parser.add_argument("--component", required=True, help="Component name or scope")
    parser.add_argument("--bump", required=True, choices=["patch", "minor", "major"])
    parser.add_argument("--manifest", required=False)
    parser.add_argument("--no-update-manifest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", required=False)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    config = load_yaml(repo_root / args.config)
    component_name = resolve_component_name(config, args.component)
    component = component_map(config)[component_name]

    bump = ensure_valid_bump(args.bump)
    current = read_component_version(repo_root, component)
    next_version = bump_semver(current, bump)

    result = {
        "name": component_name,
        "scope": component.get("scope"),
        "kind": component.get("kind"),
        "bump": bump,
        "current_version": current,
        "next_version": next_version,
        "changed_files": [],
    }

    if args.dry_run:
        print(f"Dry run: {component_name} would bump {current} -> {next_version}")
    else:
        changed_files = write_component_version(repo_root, component, next_version)
        result["changed_files"] = changed_files
        print(f"Bumped {component_name}: {current} -> {next_version}")

        manifest_path = args.manifest
        if not args.no_update_manifest:
            if not manifest_path:
                manifest_path = config.get("release", {}).get("manifest_file", "manifest.yaml")
            run_update_manifest(args.config, manifest_path)

    if args.output:
        dump_json(Path(args.output), result)


if __name__ == "__main__":
    main()
