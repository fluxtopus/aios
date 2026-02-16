#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from _common import (
    bump_rank,
    bump_semver,
    component_map,
    dump_json,
    load_json,
    load_yaml,
    read_component_version,
    scope_map,
)

HEADER_RE = re.compile(
    r"^(?P<type>[a-z]+)(\((?P<scope>[a-z0-9][a-z0-9\-/]*)\))?(?P<bang>!)?:\s.+$"
)


def get_commits(base: str, head: str) -> list[dict[str, str]]:
    fmt = "%H%x1f%s%x1f%b%x1e"
    cmd = ["git", "log", "--format=" + fmt, f"{base}..{head}"]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)

    commits: list[dict[str, str]] = []
    for record in proc.stdout.split("\x1e"):
        if not record.strip():
            continue
        parts = record.strip("\n").split("\x1f")
        if len(parts) != 3:
            continue
        commit_hash, subject, body = parts
        commits.append({"hash": commit_hash, "subject": subject.strip(), "body": body.strip()})
    return commits


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute semver bumps from conventional commits")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--changed", required=True, help="JSON output of detect_components.py")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    config = load_yaml(repo_root / args.config)
    changed = load_json(Path(args.changed))

    changed_components = set(changed.get("components", []))
    components_by_name = component_map(config)
    scopes = scope_map(config)

    computed_bumps: dict[str, str] = {}
    rationale: dict[str, list[str]] = {}

    commits = get_commits(args.base, args.head)

    type_bumps = config["commit"]["type_bumps"]
    require_scope = bool(config["commit"].get("require_scope", True))
    fallback_bump = config["commit"].get("default_bump_for_changed_component", "patch")

    for commit in commits:
        subject = commit["subject"]
        body = commit["body"]
        m = HEADER_RE.match(subject)
        if not m:
            continue

        commit_type = m.group("type")
        scope = m.group("scope")
        bang = bool(m.group("bang"))

        if require_scope and not scope:
            continue

        component_name = scopes.get(scope or "")
        if not component_name or component_name not in changed_components:
            continue

        bump = type_bumps.get(commit_type, "patch")
        if bang or "BREAKING CHANGE" in body or "BREAKING-CHANGE" in body:
            bump = "major"

        prev = computed_bumps.get(component_name)
        if prev is None or bump_rank(bump) > bump_rank(prev):
            computed_bumps[component_name] = bump

        rationale.setdefault(component_name, []).append(f"{commit['hash'][:8]} {subject}")

    for component_name in sorted(changed_components):
        if component_name not in computed_bumps:
            computed_bumps[component_name] = fallback_bump
            rationale.setdefault(component_name, []).append(
                f"fallback:{fallback_bump} (changed files without mapped conventional scope)"
            )

    plan_components = []
    for component_name in sorted(computed_bumps):
        component = components_by_name[component_name]
        current = read_component_version(repo_root, component)
        next_version = bump_semver(current, computed_bumps[component_name])
        plan_components.append(
            {
                "name": component_name,
                "scope": component.get("scope"),
                "kind": component.get("kind"),
                "bump": computed_bumps[component_name],
                "current_version": current,
                "next_version": next_version,
                "reasons": rationale.get(component_name, []),
            }
        )

    output = {
        "base": args.base,
        "head": args.head,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "components": plan_components,
    }

    dump_json(Path(args.output), output)
    print(f"Computed bump plan for {len(plan_components)} component(s)")


if __name__ == "__main__":
    main()
