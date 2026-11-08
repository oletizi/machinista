#!/usr/bin/env bash
# Build (if needed) and run Machinista on an x86-64 Linux desktop without sudo.
# Native dependencies may come from the distro or Homebrew; see docs/BUILD.md.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x build/audio_engine || "${REBUILD:-0}" == 1 ]]; then
  flags=()
  if command -v brew >/dev/null 2>&1; then
    # Brew's hidapi.pc points inside include/hidapi; the code includes <hidapi/hidapi.h>.
    flags+=("-DCMAKE_CXX_FLAGS=-I$(brew --prefix)/include")
  fi
  cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release "${flags[@]}"
  cmake --build build --parallel "$(nproc)"
fi

# Use an interpreter that has Pillow; Homebrew's python3 often shadows the
# system one on PATH without it. Override with PYTHON=/path/to/python3.
if [[ -z "${PYTHON:-}" ]]; then
  for candidate in python3 /usr/bin/python3; do
    if "$candidate" -c 'import PIL' 2>/dev/null; then PYTHON="$candidate"; break; fi
  done
fi
if [[ -z "${PYTHON:-}" ]]; then
  echo "No python3 with Pillow found; install it (pip install -r requirements-dev.txt) or set PYTHON" >&2
  exit 1
fi
exec "$PYTHON" tools/machinista.py "$@"
