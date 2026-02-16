#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _common import dump_yaml, load_yaml, read_component_version, write_plain_version


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap VERSION files and manifest")
    parser.add_argument("--config", required=True)
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument("--default-version", default="0.1.0")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    config = load_yaml(repo_root / args.config)

    created_files: list[str] = []
    components = config.get("components", [])

    for component in components:
        if component.get("kind") != "app":
            continue
        version_meta = component.get("version", {})
        if version_meta.get("kind") != "plain":
            continue

        rel_file = str(version_meta.get("file"))
        path = repo_root / rel_file
        if path.exists():
            continue

        created_files.append(rel_file)
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            write_plain_version(path, args.default_version)

    if not args.write:
        print("Dry run: use --write to create missing VERSION files and bootstrap manifest")

    for rel_file in created_files:
        print(f"Missing app VERSION file: {rel_file}")

    manifest_path = repo_root / args.manifest
    if args.write:
        # Write a minimal bootstrap manifest with existing component versions.
        manifest_components = {}
        for component in components:
            manifest_components[component["name"]] = {
                "scope": component.get("scope"),
                "kind": component.get("kind"),
                "version": read_component_version(repo_root, component),
            }

        dump_yaml(
            manifest_path,
            {
                "schema_version": 1,
                "platform_release": "platform-bootstrap.1",
                "components": manifest_components,
            },
        )
        print(f"Bootstrapped manifest: {args.manifest}")


if __name__ == "__main__":
    main()
