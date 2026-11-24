#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
mode="${1:---keyboard}"
if [[ "$mode" != '--keyboard' && "$mode" != '--voice' ]]; then
  echo 'Usage: bash install.sh [--keyboard|--voice]' >&2
  exit 2
fi
mkdir -p reports
exec > >(tee reports/install-latest.log) 2>&1
trap 'echo "SETUP STOPPED at line $LINENO. Full output: reports/install-latest.log"' ERR
if [[ "$(uname -m)" != "aarch64" ]]; then
  echo 'Pi deployment expects a 64-bit Raspberry Pi OS (aarch64). For desktop tests use requirements.txt.' >&2
  exit 1
fi
sudo apt update
sudo apt install -y python3-venv python3-pip python3-dev build-essential python3-tk libportaudio2 espeak-ng i2c-tools unzip alsa-utils pipewire-bin wireplumber libspa-0.2-bluetooth bluez
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
if [[ "$mode" == '--voice' ]]; then
  .venv/bin/python -m pip install -r requirements-pi.txt
# The selected ONNX backend does not use tflite-runtime. Avoid its Python wheel restriction.
.venv/bin/python -m pip install --no-deps openwakeword==0.6.0
else
  .venv/bin/python -m pip install -r requirements-hardware.txt
  .venv/bin/python -m pip check
fi
.venv/bin/python preflight.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
echo 'Software checks completed. Reboot once, reconnect, then: bash verify_pi.sh'
echo 'Voice models, microphone and Bluetooth playback are NOT validated by this setup.'
