#!/usr/bin/env bash
# Compatibility helper. The supported dependency declarations live in pyproject.toml.
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "Usage: $0 <virtual-environment-directory>" >&2
  exit 2
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Install uv first: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
uv venv "$1"
uv pip install --python "$1/bin/python" -e "${project_dir}[coverage,visualization]"
