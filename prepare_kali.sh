#!/usr/bin/env bash
set -euo pipefail

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "[!] This script must be sourced to update your current shell."
  echo "[!] Use: source ./prepare_kali.sh --all"
  exit 1
fi

python3 "$(dirname "${BASH_SOURCE[0]}")/main.py" "$@"

if [[ -f "$HOME/.bashrc" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.bashrc"
fi
