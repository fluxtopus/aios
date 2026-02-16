#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required. Install with: python3 -m pip install pyyaml"
    ) from exc

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
VERSION_ASSIGN_RE = re.compile(r'(__version__\s*=\s*["\'])([^"\']+)(["\'])')
SETUP_VERSION_RE = re.compile(r'(version\s*=\s*["\'])([^"\']+)(["\'])')
VALID_BUMPS = {"patch", "minor", "major"}


@dataclass
class VersionInfo:
    current: str
    next: str


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def ensure_semver(version: str) -> tuple[int, int, int]:
    m = SEMVER_RE.match(version.strip())
    if not m:
        raise ValueError(f"Invalid semver: {version}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump_semver(version: str, bump: str) -> str:
    major, minor, patch = ensure_semver(version)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unsupported bump type: {bump}")


def bump_rank(bump: str) -> int:
    ranks = {"patch": 1, "minor": 2, "major": 3}
    if bump not in ranks:
        raise ValueError(f"Unsupported bump type: {bump}")
    return ranks[bump]


def ensure_valid_bump(bump: str) -> str:
    if bump not in VALID_BUMPS:
        raise ValueError(f"Unsupported bump type: {bump}")
    return bump


def read_pyproject_version(path: Path) -> str:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return data["project"]["version"]


def write_pyproject_version(path: Path, new_version: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    in_project = False
    changed = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue

        if in_project and re.match(r'^version\s*=\s*"[^"]+"\s*$', stripped):
            indent = line[: len(line) - len(line.lstrip())]
            newline = "\n" if line.endswith("\n") else ""
            lines[i] = f'{indent}version = "{new_version}"{newline}'
            changed = True
            break

    if not changed:
        raise ValueError(f"Could not update [project].version in {path}")

    path.write_text("".join(lines), encoding="utf-8")


def read_setup_py_version(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    m = SETUP_VERSION_RE.search(content)
    if not m:
        raise ValueError(f"Could not find version= in {path}")
    return m.group(2)


def write_setup_py_version(path: Path, new_version: str) -> None:
    content = path.read_text(encoding="utf-8")
    updated, count = SETUP_VERSION_RE.subn(rf"\g<1>{new_version}\g<3>", content, count=1)
    if count != 1:
        raise ValueError(f"Could not update setup.py version in {path}")
    path.write_text(updated, encoding="utf-8")


def read_package_json_version(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data["version"]


def write_package_json_version(path: Path, new_version: str) -> None:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data["version"] = new_version
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def read_plain_version(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def write_plain_version(path: Path, new_version: str) -> None:
    path.write_text(f"{new_version}\n", encoding="utf-8")


def read_component_version(repo_root: Path, component: dict[str, Any]) -> str:
    version_meta = component["version"]
    version_file = repo_root / version_meta["file"]
    kind = version_meta["kind"]

    if kind == "pyproject":
        return read_pyproject_version(version_file)
    if kind == "setup-py":
        return read_setup_py_version(version_file)
    if kind == "package-json":
        return read_package_json_version(version_file)
    if kind == "plain":
        return read_plain_version(version_file)
    raise ValueError(f"Unsupported version kind: {kind}")


def write_component_version(repo_root: Path, component: dict[str, Any], new_version: str) -> list[str]:
    version_meta = component["version"]
    version_file = repo_root / version_meta["file"]
    kind = version_meta["kind"]

    if kind == "pyproject":
        write_pyproject_version(version_file, new_version)
    elif kind == "setup-py":
        write_setup_py_version(version_file, new_version)
    elif kind == "package-json":
        write_package_json_version(version_file, new_version)
    elif kind == "plain":
        write_plain_version(version_file, new_version)
    else:
        raise ValueError(f"Unsupported version kind: {kind}")

    changed_files = [str(version_meta["file"])]

    for runtime_file in component.get("runtime_version_files", []):
        runtime_path = repo_root / runtime_file
        content = runtime_path.read_text(encoding="utf-8")
        updated, count = VERSION_ASSIGN_RE.subn(rf"\g<1>{new_version}\g<3>", content, count=1)
        if count != 1:
            raise ValueError(f"Could not update __version__ in {runtime_file}")
        runtime_path.write_text(updated, encoding="utf-8")
        changed_files.append(runtime_file)

    return changed_files


def read_runtime_file_version(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    m = VERSION_ASSIGN_RE.search(content)
    if not m:
        raise ValueError(f"Could not find __version__ assignment in {path}")
    return m.group(2)


def version_source_files(component: dict[str, Any]) -> list[str]:
    files = [component["version"]["file"]]
    files.extend(component.get("runtime_version_files", []))
    return files


def digest_files(repo_root: Path, rel_files: list[str]) -> str:
    h = hashlib.sha256()
    for rel_file in sorted(rel_files):
        abs_path = repo_root / rel_file
        if not abs_path.exists():
            raise FileNotFoundError(f"Missing file for digest: {rel_file}")
        h.update(rel_file.encode("utf-8"))
        h.update(b"\x00")
        h.update(abs_path.read_bytes())
        h.update(b"\x00")
    return h.hexdigest()


def component_map(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {component["name"]: component for component in config["components"]}


def scope_map(config: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for component in config["components"]:
        scope = component.get("scope")
        if scope:
            mapping[scope] = component["name"]
    return mapping


def resolve_component_name(config: dict[str, Any], value: str) -> str:
    components = component_map(config)
    if value in components:
        return value
    scopes = scope_map(config)
    if value in scopes:
        return scopes[value]
    raise ValueError(f"Unknown component or scope: {value}")


def component_matches_file(component: dict[str, Any], rel_file: str) -> bool:
    from fnmatch import fnmatch

    for pattern in component.get("path_globs", []):
        if fnmatch(rel_file, pattern):
            return True
    return False
