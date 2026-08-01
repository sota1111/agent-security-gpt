#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$repo_root/.venv/bin/python"

if [[ ! -x "$python_bin" ]]; then
  echo "restart gate FAIL: expected repository interpreter at $python_bin" >&2
  exit 1
fi

cd "$repo_root"
"$python_bin" scripts/verify_sdk_contract.py
"$python_bin" scripts/test_exec_compat.py
"$python_bin" -m compileall -q attack.py eval tests
"$python_bin" -m pytest -q
echo "restart gate PASS: SDK, payload identity, exec compatibility, and tests"
