#!/usr/bin/env bash
# scripts/release.sh

# Releases an Atlas version

pipx run build

twin check dist/*

twine upload dist/*
