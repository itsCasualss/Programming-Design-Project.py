#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "$0")"
export PA_ALSA_PLUGHW=1
export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

mkdir -p logs
exec flock --nonblock --no-fork logs/smartjeong.lock \
    .venv/bin/python main.py --dsi --voice >> logs/desktop-launch.log 2>&1
