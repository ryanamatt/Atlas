#!/usr/bin/env bash
# scripts/release.sh

# Releases an Atlas version

set -euo pipefail

# Build the package using uv's build tool execution
uvx build

# Check and upload using twine via uvx
uvx twine check dist/*

uvx twine upload dist/*
