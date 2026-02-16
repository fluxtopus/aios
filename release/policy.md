# Release Policy

## Versioning Model

- Components (apps/packages) use independent SemVer.
- A platform release is a snapshot of component versions in `manifest.yaml`.
- Cross-component version equality is not required.

## Bump Rules

- `patch`: backward-compatible fixes/maintenance
- `minor`: backward-compatible features
- `major`: breaking changes

Bump intent is declared in `.changes/*.yaml`.

## Release Cadence

- Default cadence: per merge to `main` when pending `.changes` notes exist.
- Release preparation is automated into a release PR.
- Publish happens only after release PR merge and explicit approval.

## Sources Of Truth

- Component definitions and version source files: `release/components.yaml`
- Pending release metadata: `.changes/`
- Platform snapshot: `manifest.yaml`
- Generated release plan: `release/latest-release-plan.json`

## Required PR Metadata

For any PR changing a tracked component path:

- Add at least one `.changes/*.yaml` note with `component`, `bump`, and `summary`.

## Tagging

- Component tags: `component-name@x.y.z`
- Platform tags: `platform-YYYY.MM.DD.N`
- Tags are immutable. Existing tags must not be replaced.

## Rollback Principle

- Rollback decisions use prior `platform-*` tag manifests as authoritative snapshots.
- Any rollback must regenerate `manifest.yaml` and pass version-sync checks.
