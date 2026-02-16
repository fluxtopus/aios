#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGES_DIR="${ROOT_DIR}/packages"

MODE="build"
INDEX="pypi"
PUBLISH_URL="https://upload.pypi.org/legacy/"
declare -a SELECTED_PACKAGES=()

usage() {
    cat <<'EOF'
Build and optionally publish Python packages under ./packages using uv.

Usage:
  ./scripts/publish-python-packages.sh [--build-only] [--publish] [--index pypi|testpypi] [--package <dir>]

Options:
  --build-only        Build wheel/sdist only (default).
  --publish           Build and publish.
  --index <name>      pypi (default) or testpypi.
  --package <dir>     Restrict to package directory under ./packages. Repeatable.
  -h, --help          Show help.

Environment:
  UV_PUBLISH_TOKEN    Optional token for uv publish.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --build-only)
            MODE="build"
            ;;
        --publish)
            MODE="publish"
            ;;
        --index)
            INDEX="$2"
            shift
            ;;
        --package)
            SELECTED_PACKAGES+=("$2")
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            exit 1
            ;;
    esac
    shift
done

if [[ "${INDEX}" == "testpypi" ]]; then
    PUBLISH_URL="https://test.pypi.org/legacy/"
elif [[ "${INDEX}" != "pypi" ]]; then
    echo "--index must be pypi or testpypi" >&2
    exit 1
fi

UV_BIN=""
if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
elif [[ -x "${HOME}/.local/bin/uv" ]]; then
    UV_BIN="${HOME}/.local/bin/uv"
else
    echo "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

if [[ "${MODE}" == "publish" && -z "${UV_PUBLISH_TOKEN:-}" ]]; then
    echo "Warning: UV_PUBLISH_TOKEN not set; uv will use other configured auth." >&2
fi

declare -a package_dirs=()
if [[ ${#SELECTED_PACKAGES[@]} -gt 0 ]]; then
    for pkg in "${SELECTED_PACKAGES[@]}"; do
        package_dirs+=("${PACKAGES_DIR}/${pkg}")
    done
else
    while IFS= read -r dir; do
        package_dirs+=("${dir}")
    done < <(find "${PACKAGES_DIR}" -mindepth 1 -maxdepth 1 -type d | sort)
fi

declare -a python_dirs=()
for dir in "${package_dirs[@]}"; do
    if [[ ! -d "${dir}" ]]; then
        echo "Package directory not found: ${dir}" >&2
        exit 1
    fi
    if [[ -f "${dir}/pyproject.toml" || -f "${dir}/setup.py" ]]; then
        python_dirs+=("${dir}")
    fi
done

if [[ ${#python_dirs[@]} -eq 0 ]]; then
    echo "No Python packages selected" >&2
    exit 1
fi

for dir in "${python_dirs[@]}"; do
    name="$(basename "${dir}")"
    echo "==> ${name}"

    (
        cd "${dir}"
        rm -rf dist build ./*.egg-info
        "${UV_BIN}" build

        if [[ "${MODE}" == "publish" ]]; then
            "${UV_BIN}" publish --publish-url "${PUBLISH_URL}"
        fi
    )
done

echo "Completed ${MODE} for ${#python_dirs[@]} package(s)."
