#!/usr/bin/env bash
# scripts/format.sh

# Lints and formats the Atlas codebase with Ruff.
#
# Usage:
#   ./format.sh           Apply lint fixes and format the code.
#   ./format.sh --check   Report problems without changing files (for CI).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v ruff >/dev/null 2>&1; then
    echo "error: ruff is not installed. Install it with: pip install ruff" >&2
    exit 1
fi

status=0
TARGET="${2:-.}"

case "${1:-}" in
    "")
        ruff check --fix "$TARGET" || status=1
        ruff format "$TARGET"
        ;;
    --check)
        ruff check "$TARGET" || status=1
        ruff format --check "$TARGET" || status=1
        ;;
    *)
        echo "usage: ./scripts/format.sh [--check] [path]" >&2
        exit 2
        ;;
esac

exit "$status"
