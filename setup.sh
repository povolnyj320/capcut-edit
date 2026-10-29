#!/bin/zsh
# One-time setup on an Apple Silicon Mac: Python venv, Whisper, ffmpeg, the HyperFrames CLI.
set -e
cd "$(dirname "$0")"

if [ "$(uname -m)" != "arm64" ]; then
  echo "This needs an Apple Silicon Mac (mlx-whisper runs on the Apple GPU)."
  exit 1
fi

python3 -m venv .venv
.venv/bin/pip install -q -U pip
.venv/bin/pip install -q -r requirements.txt
mkdir -p "${CAPCUT_EDIT_WORK:-$HOME/Movies/capcut-edit-work}"

if ! command -v hyperframes >/dev/null 2>&1; then
  if command -v npm >/dev/null 2>&1; then
    echo "Installing the HyperFrames CLI..."
    npm install -g hyperframes@0.8.200
  else
    echo "Node 20+ is not installed. Motion graphics need it: https://nodejs.org, then: npm install -g hyperframes@0.8.200"
  fi
fi
hyperframes telemetry disable >/dev/null 2>&1 || true

echo
echo "Done. Next:"
echo "  1. In CapCut desktop, make one empty project (call it Empty) and quit CapCut (Cmd+Q)."
echo "  2. Save your templates from one finished reel that has captions, B-roll and music:"
echo "       .venv/bin/python -I capcut.py style \"<that reel's name>\""
echo "  3. Fill in edit-style.md, then open Claude Code in this folder and run /capcut-edit."
