#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

from _common import dump_json, load_json, load_yaml


def load_pending_note_summaries(notes_dir: Path) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    for path in sorted(notes_dir.glob("*.y*ml")):
        if path.name.startswith("_"):
            continue
        data = load_yaml(path)
        if not isinstance(data, dict):
            continue
        notes.append(
            {
                "file": path.name,
                "component": str(data.get("component", "")).strip(),
                "bump": str(data.get("bump", "")).strip(),
                "summary": str(data.get("summary", "")).strip(),
            }
        )
    return notes


def prepend_changelog_entry(changelog_path: Path, entry: str) -> None:
    changelog_path.parent.mkdir(parents=True, exist_ok=True)
    if changelog_path.exists():
        previous = changelog_path.read_text(encoding="utf-8").strip()
        header = "# Platform Changelog"
        if previous.startswith(header):
            rest = previous[len(header):].strip()
            if rest:
                content = f"{header}\n\n{entry.strip()}\n\n{rest}\n"
            else:
                content = f"{header}\n\n{entry.strip()}\n"
        else:
            content = entry.strip() + "\n\n" + previous + "\n"
    else:
        content = "# Platform Changelog\n\n" + entry.strip() + "\n"
    changelog_path.write_text(content, encoding="utf-8")


def archive_notes(notes_dir: Path, archive_dir: Path) -> list[str]:
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived: list[str] = []

    for path in sorted(notes_dir.glob("*.y*ml")):
        if path.name.startswith("_"):
            continue
        dest = archive_dir / path.name
        shutil.move(str(path), dest)
        archived.append(str(dest))

    return archived


def build_changelog_entry(
    platform_release: str,
    release_date: str,
    plan_components: list[dict],
    notes: list[dict[str, str]],
) -> str:
    lines = [f"## {platform_release} ({release_date})", "", "### Version bumps", ""]

    if not plan_components:
        lines.append("- No component version bumps")
    else:
        for item in plan_components:
            lines.append(
                f"- `{item['name']}`: `{item['current_version']}` -> `{item['next_version']}` ({item['bump']})"
            )

    lines.extend(["", "### Included changes", ""])

    if not notes:
        lines.append("- No release notes were provided")
    else:
        for note in notes:
            lines.append(
                f"- `{note['component']}` ({note['bump']}): {note['summary']} "
                f"[`{note['file']}`]"
            )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize release metadata")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--changes-dir", required=True)
    parser.add_argument("--changelog", required=True)
    parser.add_argument("--archive-root", required=True)
    parser.add_argument("--release-plan-output", required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    plan_path = repo_root / args.plan
    manifest_path = repo_root / args.manifest
    changes_dir = repo_root / args.changes_dir
    changelog_path = repo_root / args.changelog
    archive_root = repo_root / args.archive_root
    release_plan_output = repo_root / args.release_plan_output

    plan = load_json(plan_path)
    manifest = load_yaml(manifest_path)

    platform_release = str(manifest.get("platform_release", "")).strip()
    if not platform_release:
        raise SystemExit("manifest is missing platform_release")

    release_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    notes = load_pending_note_summaries(changes_dir)

    changelog_entry = build_changelog_entry(
        platform_release,
        release_date,
        plan.get("components", []),
        notes,
    )
    prepend_changelog_entry(changelog_path, changelog_entry)

    archive_dir = archive_root / platform_release
    archived_files = archive_notes(changes_dir, archive_dir)

    release_plan = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform_release": platform_release,
        "git_sha": manifest.get("git_sha"),
        "manifest": args.manifest,
        "components": plan.get("components", []),
        "notes": notes,
        "archived_notes": [str(Path(path).relative_to(repo_root)) for path in archived_files],
        "changelog": args.changelog,
    }

    dump_json(release_plan_output, release_plan)

    print(f"Updated changelog: {args.changelog}")
    print(f"Archived {len(archived_files)} note(s) to {archive_dir.relative_to(repo_root)}")
    print(f"Wrote release plan: {args.release_plan_output}")


if __name__ == "__main__":
    main()
