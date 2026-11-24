#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
mkdir -p reports
exec > >(tee reports/pi-verification-latest.log) 2>&1
trap 'echo "CHECK STOPPED at line $LINENO. Send reports/pi-verification-latest.log; do not change wiring while powered."' ERR
export GPIOZERO_PIN_FACTORY=rpigpio
.venv/bin/python preflight.py --hardware
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python tft_test.py
.venv/bin/python main.py --demo --hardware --no-audio
echo 'Sequence finished. Confirm TFT colors/text and separate LED activity visually.'
echo 'The demo includes an intentional unrecognized-command error screen.'
echo 'Audio and microphone were deliberately skipped, not passed.'
echo 'Interactive keyboard mode: GPIOZERO_PIN_FACTORY=rpigpio .venv/bin/python main.py --offline --no-audio'
