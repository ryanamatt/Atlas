#!/usr/bin/env bash
#
# clean-caches.sh
#
# Removes Python caches and build artifacts from the repository so you can
# start from a clean tree.
#
# Usage:
#   ./clean-caches.sh              Delete everything listed below.
#   ./clean-caches.sh -n           Dry run: only list what would be deleted.
#   ./clean-caches.sh -h           Show this help.
#
# Removed anywhere in the repo:
#   __pycache__/  .pytest_cache/  .ruff_cache/  .mypy_cache/  .hypothesis/
#   .tox/  .nox/  *.egg-info/  *.pyc  *.pyo  .coverage  .coverage.*  coverage.xml
#
# Removed at the repo root only:
#   build/  dist/  htmlcov/  .eggs/
#
# Never touched: .git, .venv, venv, node_modules.

set -euo pipefail

DRY_RUN=0

usage() {
    sed -n '3,19p' "$0" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
    case "$arg" in
        -n | --dry-run) DRY_RUN=1 ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            usage >&2
            exit 2
            ;;
    esac
done

# Work from the git root when inside a repo, otherwise from the current directory.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

targets=()

# Caches and artifacts that can appear at any depth.
while IFS= read -r -d '' path; do
    targets+=("$path")
done < <(
    find . \
        \( -name .git -o -name .venv -o -name venv -o -name node_modules \) -prune -o \
        \( -type d \( \
            -name __pycache__ -o \
            -name .pytest_cache -o \
            -name .ruff_cache -o \
            -name .mypy_cache -o \
            -name .hypothesis -o \
            -name .tox -o \
            -name .nox -o \
            -name '*.egg-info' \
        \) -print0 -prune \) -o \
        \( -type f \( \
            -name '*.pyc' -o \
            -name '*.pyo' -o \
            -name .coverage -o \
            -name '.coverage.*' -o \
            -name coverage.xml \
        \) -print0 \)
)

# Build output, only at the repo root so a source package named "build" is safe.
for name in build dist htmlcov .eggs; do
    if [[ -e "./$name" ]]; then
        targets+=("./$name")
    fi
done

if [[ ${#targets[@]} -eq 0 ]]; then
    echo "Nothing to clean."
    exit 0
fi

for path in "${targets[@]}"; do
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "would remove ${path#./}"
    else
        rm -rf -- "$path"
        echo "removed ${path#./}"
    fi
done

if [[ $DRY_RUN -eq 1 ]]; then
    echo "Dry run: ${#targets[@]} item(s) would be removed."
else
    echo "Done: ${#targets[@]} item(s) removed."
fi
