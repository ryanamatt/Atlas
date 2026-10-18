#!/usr/bin/env bash
# scripts/release.sh

# Releases an Atlas version

python -m build

twin check dist/*

twine upload dist/*
