#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import (
    bump_rank,
    bump_semver,
    component_map,
    dump_json,
    ensure_valid_bump,
    load_json,
    load_yaml,
    read_component_version,
    resolve_component_name,
)


def parse_note(path: Path) -> dict[str, Any]:
    note = load_yaml(path)
    if not isinstance(note, dict):
        raise ValueError("note must be a YAML object")

    for field in ("component", "bump", "summary"):
        if field not in note:
            raise ValueError(f"missing required field: {field}")

    component = str(note["component"]).strip()
    bump = ensure_valid_bump(str(note["bump"]).strip())
    summary = str(note["summary"]).strip()
    if not summary:
        raise ValueError("summary cannot be empty")

    return {
        "component": component,
        "bump": bump,
        "summary": summary,
    }


def load_notes(notes_dir: Path) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for path in sorted(notes_dir.glob("*.y*ml")):
        if path.name.startswith("_"):
            continue
        note = parse_note(path)
        note["file"] = str(path)
        notes.append(note)
    return notes


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute semver bumps from .changes notes")
    parser.add_argument("--config", required=True)
    parser.add_argument("--changes-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--changed",
        required=False,
        help="Optional JSON output of detect_components.py to filter to changed components",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    config = load_yaml(repo_root / args.config)
    components = component_map(config)

    notes_dir = (repo_root / args.changes_dir).resolve()
    if not notes_dir.exists():
        raise SystemExit(f"changes dir does not exist: {notes_dir}")

    changed_filter: set[str] | None = None
    if args.changed:
        changed = load_json(Path(args.changed))
        changed_filter = set(changed.get("components", []))

    notes = load_notes(notes_dir)

    if not notes:
        dump_json(
            Path(args.output),
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": "changes",
                "changes_dir": str(Path(args.changes_dir)),
                "components": [],
                "notes": [],
            },
        )
        print("No pending .changes notes found")
        return

    aggregated_bumps: dict[str, str] = {}
    reasons: dict[str, list[str]] = {}

    for note in notes:
        component_name = resolve_component_name(config, note["component"])
        if changed_filter is not None and component_name not in changed_filter:
            continue

        if component_name not in components:
            raise SystemExit(f"Unknown component in note {note['file']}: {note['component']}")

        bump = note["bump"]
        previous = aggregated_bumps.get(component_name)
        if previous is None or bump_rank(bump) > bump_rank(previous):
            aggregated_bumps[component_name] = bump

        reasons.setdefault(component_name, []).append(f"{Path(note['file']).name}: {note['summary']}")

    plan_components = []
    for component_name in sorted(aggregated_bumps):
        component = components[component_name]
        current = read_component_version(repo_root, component)
        bump = aggregated_bumps[component_name]
        next_version = bump_semver(current, bump)

        plan_components.append(
            {
                "name": component_name,
                "scope": component.get("scope"),
                "kind": component.get("kind"),
                "bump": bump,
                "current_version": current,
                "next_version": next_version,
                "reasons": reasons.get(component_name, []),
            }
        )

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "changes",
        "changes_dir": str(Path(args.changes_dir)),
        "components": plan_components,
        "notes": [
            {
                "file": Path(note["file"]).name,
                "component": resolve_component_name(config, note["component"]),
                "bump": note["bump"],
                "summary": note["summary"],
            }
            for note in notes
        ],
    }

    dump_json(Path(args.output), output)
    print(f"Computed bump plan for {len(plan_components)} component(s) from .changes notes")


if __name__ == "__main__":
    main()
