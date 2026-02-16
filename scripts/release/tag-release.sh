#!/usr/bin/env bash
set -euo pipefail

PLAN_FILE=""
MANIFEST_FILE="manifest.yaml"
PUSH_TAGS="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan)
      PLAN_FILE="$2"
      shift 2
      ;;
    --manifest)
      MANIFEST_FILE="$2"
      shift 2
      ;;
    --push)
      PUSH_TAGS="true"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${PLAN_FILE}" ]]; then
  echo "--plan is required" >&2
  exit 1
fi

while IFS='|' read -r name version; do
  tag="${name}@${version}"
  if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null; then
    echo "Tag already exists and will not be replaced: ${tag}" >&2
    exit 1
  fi
  git tag -a "${tag}" -m "Release ${tag}"
  echo "Created tag: ${tag}"
done < <(python3 - <<'PY' "${PLAN_FILE}"
import json
import sys
from pathlib import Path

plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for item in plan.get("components", []):
    print(f"{item['name']}|{item['next_version']}")
PY
)

platform_tag="$(python3 - <<'PY' "${MANIFEST_FILE}"
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:
    raise SystemExit("PyYAML is required to read manifest") from exc

manifest = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(manifest["platform_release"])
PY
)"

if ! git rev-parse -q --verify "refs/tags/${platform_tag}" >/dev/null; then
  git tag -a "${platform_tag}" -m "Platform release ${platform_tag}"
  echo "Created tag: ${platform_tag}"
else
  echo "Tag already exists and will not be replaced: ${platform_tag}" >&2
  exit 1
fi

if [[ "${PUSH_TAGS}" == "true" ]]; then
  git push origin --tags
fi
