# SmartJeong project context

SmartJeong is Team 4's Python personal briefing assistant on a Raspberry Pi. The presentation setup uses the DSI touchscreen and can accept voice and touch in the same session. The repository root contains the team's earlier work. The runnable presentation snapshot is this folder. Use [README.md](README.md) for deployment and verification.

## Flow and file map

- `main.py` drives the interaction: idle → prompt → listening → processing → output → idle. A person can say “Hey Jarvis” or tap Wake, then say a service name or tap its tile.
- `dashboard.py` owns the Tkinter touchscreen UI, news dialog, and touch input. `display_interface.py` delivers display updates and supports the legacy display path.
- `voice_interface.py` handles microphone capture, openWakeWord detection, and Vosk recognition. `austin_adapter.py` reuses Austin's grammar and command parser in `vendor/austin/voice_interface/`. The microphone stays open through the greeting to capture the first command. Touch actions go to the same interaction worker in voice mode.
- `services.py` provides Schedule (iCal), Pills (local JSON reminders), Weather (Open-Meteo), and News (RSS). `news_search.py` handles news choices and queries. `presenter.py` formats a common result for the display and speech, and `speech_output.py` handles playback. `gpio_control.py` drives the status LED.
- `config.py` merges tracked defaults in `config.json` with the Pi's private `config.local.json`. `setup_personal.py` configures the calendar or reminders. The `data/` files in GitHub are demo fixtures.
- `launch_smartjeong.sh` starts fullscreen DSI voice mode. `enable_autostart.py` sets up desktop launch and login startup. `install_update.py` updates an existing Pi checkout and makes a backup.

## Last known state and verification

- Don saved the SmartJeong Demo calendar feed on the Pi. The demo calendar covers presentation week, November 30 through December 6, 2026. The Pi should show the current day's events once the configured feed is reachable. Voice and the display had been exercised on the Pi. The old installed build still ignored touchscreen wake and service taps in voice mode.
- This source snapshot integrates the wake and touch changes. Don handed off the Pi before applying the touch update. Verify both mixed-input paths and all four services on the actual Pi using the README checklist, then put the actual results into the final report.
- The snapshot uses Austin's updated speech-recognition source from upstream `96368ad270226ce268ce49cfa0e04e0e9ed58d9a`. The earlier root-level source, releases, and enclosure archive are available in the same repository.
- Run software tests from this folder with `python -m pip install -r requirements.txt` and `python -m unittest discover -s tests -p 'test_*.py'`. They exercise software paths using mocks and fixtures where appropriate. Successful software checks do not establish physical touchscreen response, microphone accuracy, audio routing, or live calendar access.

## Give this to your AI

Provide this file and the README, the commit SHA, Pi OS and Python version, the exact command and error, and only the relevant source files or redacted log lines. Say what has already been run and what you expected to happen. Ask for a minimal, reviewable diff and explicit verification steps. Follow the team change rules in the README.
