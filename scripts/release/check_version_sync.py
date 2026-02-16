#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _common import (
    component_map,
    ensure_semver,
    load_yaml,
    read_component_version,
    read_runtime_file_version,
)


def validate_component_versions(repo_root: Path, config: dict) -> list[str]:
    errors: list[str] = []

    for component_name, component in sorted(component_map(config).items()):
        try:
            version = read_component_version(repo_root, component)
            ensure_semver(version)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{component_name}: invalid source version ({exc})")
            continue

        version_file = repo_root / component["version"]["file"]
        if not version_file.exists():
            errors.append(f"{component_name}: missing version file {component['version']['file']}")

        for runtime_file in component.get("runtime_version_files", []):
            runtime_path = repo_root / runtime_file
            if not runtime_path.exists():
                errors.append(f"{component_name}: missing runtime version file {runtime_file}")
                continue

            try:
                runtime_version = read_runtime_file_version(runtime_path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{component_name}: could not parse {runtime_file} ({exc})")
                continue

            if runtime_version != version:
                errors.append(
                    f"{component_name}: runtime version drift in {runtime_file} "
                    f"(expected {version}, found {runtime_version})"
                )

    return errors


def validate_manifest(repo_root: Path, config: dict, manifest_path: Path) -> list[str]:
    if not manifest_path.exists():
        return [f"manifest file does not exist: {manifest_path}"]

    manifest = load_yaml(manifest_path)
    errors: list[str] = []

    if "components" not in manifest or not isinstance(manifest["components"], dict):
        return [f"manifest missing components map: {manifest_path}"]

    components = component_map(config)

    for name, component in sorted(components.items()):
        manifest_component = manifest["components"].get(name)
        if not manifest_component:
            errors.append(f"manifest missing component: {name}")
            continue

        source_version = read_component_version(repo_root, component)
        manifest_version = str(manifest_component.get("version", ""))
        if source_version != manifest_version:
            errors.append(
                f"manifest version mismatch for {name}: "
                f"source={source_version}, manifest={manifest_version}"
            )

        source_scope = component.get("scope")
        manifest_scope = manifest_component.get("scope")
        if source_scope != manifest_scope:
            errors.append(
                f"manifest scope mismatch for {name}: source={source_scope}, manifest={manifest_scope}"
            )

        source_kind = component.get("kind")
        manifest_kind = manifest_component.get("kind")
        if source_kind != manifest_kind:
            errors.append(
                f"manifest kind mismatch for {name}: source={source_kind}, manifest={manifest_kind}"
            )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate component version sync")
    parser.add_argument("--config", required=True)
    parser.add_argument("--manifest", required=False)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    config = load_yaml(repo_root / args.config)

    errors = validate_component_versions(repo_root, config)

    if args.manifest:
        errors.extend(validate_manifest(repo_root, config, repo_root / args.manifest))

    if errors:
        print("Version sync validation failed:")
        for err in errors:
            print(f"- {err}")
        raise SystemExit(1)

    print("Version sync validation passed")


if __name__ == "__main__":
    main()
