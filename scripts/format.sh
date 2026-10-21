#!/usr/bin/env bash
# scripts/format.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

status=0
TARGET="${2:-.}"

case "${1:-}" in
    "")
        uv run ruff check --fix "$TARGET" || status=1
        uv run ruff format "$TARGET"
        ;;
    --check)
        uv run ruff check "$TARGET" || status=1
        uv run ruff format --check "$TARGET" || status=1
        ;;
    *)
        echo "usage: ./scripts/format.sh [--check] [path]" >&2
        exit 2
        ;;
esac

exit "$status"
