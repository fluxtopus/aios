#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import component_map, digest_files, dump_yaml, load_yaml, read_component_version, version_source_files


def git_sha() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def next_platform_release_id(existing_manifest: dict[str, Any] | None) -> str:
    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("platform-%Y.%m.%d")

    if not existing_manifest:
        return f"{date_prefix}.1"

    current = str(existing_manifest.get("platform_release", ""))
    if not current.startswith(date_prefix + "."):
        return f"{date_prefix}.1"

    try:
        current_n = int(current.rsplit(".", 1)[1])
    except (ValueError, IndexError):
        return f"{date_prefix}.1"
    return f"{date_prefix}.{current_n + 1}"


def component_manifest_entry(repo_root: Path, component: dict[str, Any]) -> dict[str, Any]:
    source_files = version_source_files(component)
    return {
        "scope": component.get("scope"),
        "kind": component.get("kind"),
        "version": read_component_version(repo_root, component),
        "version_sources": source_files,
        "version_sources_digest": digest_files(repo_root, source_files),
        "artifact": {
            "publish_dir": component.get("publish_dir"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate platform release manifest")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", default="manifest.yaml")
    parser.add_argument("--platform-release", required=False)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    config = load_yaml(repo_root / args.config)

    output_path = (repo_root / args.output).resolve()
    existing = load_yaml(output_path) if output_path.exists() else None

    components = component_map(config)
    manifest_components = {}
    for name in sorted(components):
        component = components[name]
        manifest_components[name] = component_manifest_entry(repo_root, component)

    platform_release = args.platform_release or next_platform_release_id(existing)

    manifest = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "platform_release": platform_release,
        "git_sha": git_sha(),
        "components": manifest_components,
    }

    dump_yaml(output_path, manifest)
    print(f"Updated manifest: {args.output}")
    print(f"Platform release: {manifest['platform_release']}")


if __name__ == "__main__":
    main()
