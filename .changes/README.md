# Pending Release Notes

Every PR that changes a tracked component must add one YAML file in this folder.

## File naming

Use:

`YYYYMMDDHHMMSS-<component>-<slug>.yaml`

Example:

`20260216094500-app-tentacle-fix-workflow-timeout.yaml`

## Schema

```yaml
component: app-tentacle
bump: patch
summary: "Fix timeout handling for long-running workflows"
```

Allowed `bump` values: `patch`, `minor`, `major`.

`component` can be a component name from `release/components.yaml` or a scope alias such as `tentacle`.

## Lifecycle

1. PRs add notes here.
2. Release PR consumes all notes in this folder.
3. Consumed notes are moved to `releases/notes/<platform-release>/`.
