# SmartJeong final handoff

SmartJeong is Team 4's Raspberry Pi personal briefing assistant. This folder contains the complete application with the wake audio and touch updates integrated. Use it to update the Pi's existing `Briefing_Box_Project` installation. Read [Project Context](PROJECT_CONTEXT.md) for the file map, known Pi state, and what to give an AI when troubleshooting.

**Before the presentation:** Update the Pi, run the hardware checklist below, and send the team the outcome and the commit used. The previous Pi session saved the SmartJeong Demo calendar configuration. The touch update had yet to be installed or verified on the Pi.

## 1. Connect to the Raspberry Pi

1. Power on the Pi and connect your laptop to the same network. On the Pi's desktop, open Terminal and run `whoami` and `hostname -I`. Record the username and the IPv4 address on the shared network. The last username was `jeong`. Use the address shown today. If SSH is disabled, on the Pi run `sudo raspi-config`, then enable **Interface Options → SSH**.
2. On the laptop, open **PowerShell** on Windows or **Terminal** on macOS/Linux. In the commands below, replace `PI_USER` and `PI_IP` with your values. At the password prompt, type the Pi account password and press Enter. The terminal hides the characters.
3. Check you are on the Pi and can see the installed app, then return to your laptop shell.

   ```sh
   ssh PI_USER@PI_IP
   hostname
   cd ~/Desktop/Briefing_Box_Project
   ls main.py .venv/bin/python
   exit
   ```

If SSH times out, check the Pi address and network again. A network may block direct device-to-device traffic. If the host key changes, verify the Pi's identity before accepting a replacement key. [Raspberry Pi remote access documentation](https://www.raspberrypi.com/documentation/computers/remote-access.html)

## 2. Transfer and apply the release

1. On the Pi, close SmartJeong from its **Close** button. On the laptop, open the directory where you want the repo copy. On Windows, if Git is unavailable, use GitHub's **Code → Download ZIP**, extract it on the laptop, and run the copy command from the extracted repository root.
2. From the laptop, clone and copy the source folder. The remote staging directory must be separate from the running application. Use a new staging directory name if retrying from a different revision.

   ```sh
   git clone -c core.autocrlf=false https://github.com/itsCasualss/Programming-Design-Project.py.git
   cd Programming-Design-Project.py
   git rev-parse HEAD
   ssh PI_USER@PI_IP "mkdir ~/smartjeong-handoff"
   scp -r ./SmartJeong_Final PI_USER@PI_IP:smartjeong-handoff/
   ssh PI_USER@PI_IP
   ```

   Save the commit SHA shown by `git rev-parse HEAD` in your test notes. If using Download ZIP, record the SHA shown on GitHub for the ref you downloaded.

3. Run these commands **on the Pi**. The updater prints a backup path. Record it. It updates the application source while preserving the target's existing configs, data, virtual environment, models, and logs.

   ```sh
   umask 077
   python3 ~/smartjeong-handoff/SmartJeong_Final/install_update.py ~/Desktop/Briefing_Box_Project
   cd ~/Desktop/Briefing_Box_Project
   bash launch_smartjeong.sh
   ```

   The launch command stays attached to your terminal until the app closes. The Pi must have an active desktop session. To install the application/desktop shortcuts and launch-on-login entry, run `.venv/bin/python enable_autostart.py` from the app directory, then verify after signing out and back in. An existing compatible desktop shortcut can reopen the app normally. To check startup problems, run `tail -n 60 logs/desktop-launch.log` from a second SSH session.

### If a prerequisite is missing

- **Existing Pi environment:** Try the update first with the installed `.venv` and models. If Python reports missing imports or models, use the setup commands below from the app directory. Run them from the Pi account that launches the desktop. `install.sh --voice` installs OS and Python dependencies for 64-bit Raspberry Pi OS. Model setup requires internet access. After a fresh install, start from the Pi desktop, or use SSH with the Pi desktop already logged in.
- **No app folder:** From the Pi, run `cp -R ~/smartjeong-handoff/SmartJeong_Final ~/Desktop/Briefing_Box_Project` once, then use the fresh setup commands.
- **Fresh setup commands:**

  ```sh
  cd ~/Desktop/Briefing_Box_Project
  bash install.sh --voice
  .venv/bin/python setup_models.py
  bash launch_smartjeong.sh
  ```

- **Calendar:** The existing Pi should retain the SmartJeong Demo feed. On a fresh install, run `.venv/bin/python setup_personal.py calendar` in the Pi terminal or an interactive SSH session. Choose `f` and enter the **secret iCal address** for the demo calendar at the hidden prompt. Restart the app. Keep the feed URL and private config off GitHub, team chats, screenshots, and AI prompts.
- **Microphone and speaker:** Run `arecord -l` to check that the USB mic is present. Test system audio on the Pi desktop and select the intended output there. The launcher includes the ALSA compatibility setting used for the USB mic. For a quick display/input smoke test, open a Pi desktop terminal and run `.venv/bin/python main.py --dsi --offline --no-audio`. The offline path does not verify Google Calendar, live services, or audio.

### Rollback

Close the app. In the following command, replace `BACKUP_NAME` with the backup directory name printed by the updater. It restores the previous files over the app directory. Runtime assets omitted from the backup stay in place, and any release-only files remain on disk.

```sh
cp -a "$HOME/Desktop/BACKUP_NAME/." "$HOME/Desktop/Briefing_Box_Project/"
cd ~/Desktop/Briefing_Box_Project
bash launch_smartjeong.sh
```

## 3. Test the presentation build on the Pi

| Test | Pass condition |
|---|---|
| Fresh launch and desktop relaunch | Home screen fits the DSI display. Close and reopen successfully. Verify launch on login if enabled. |
| Spoken wake → touch | Say “Hey Jarvis,” then tap each service tile in separate runs. Every tile opens its own briefing. |
| Touch wake → speech | Tap **Wake / Return home** from standby. Say **Schedule** once and confirm it opens. |
| Return home | Tap **Return home** during a briefing and confirm standby returns. Test tap-to-return from the menu too. |
| Four briefings | Confirm both screen and speaker output. Schedule shows today's live **SmartJeong Demo** events. Pills uses the configured demo reminders. Weather and News return results with network access. |
| News choices | Verify **Hot topics**, touchscreen keyword search, and **Cancel**. Try spoken choices separately if time permits. |
| Recovery | Give an unrecognized command or allow a timeout. Confirm it recovers and accepts a new wake action. Confirm GPIO LED behavior if connected. |

Send the team the commit, each test's pass/fail result, and any error with the exact command and relevant log lines. Avoid posting private settings or calendar links. Report software checks and Pi checks separately.

## Team change rules

- **Notify the whole team about every code change at this stage**, including one-off Pi edits. State the files changed, why, the commit or diff, and how it was tested. Record any Pi-only fix in GitHub before calling it part of the final build.
- **Verify every AI-assisted change yourself.** Read the complete diff, account for every changed file, run the relevant tests, and verify affected hardware paths on the Pi. Revert unexpected edits and report any checks that are still pending.
- **When using ChatGPT to change the codebase, use Work Mode.** Use **GPT-6.2 Sol, Medium reasoning or higher** for larger data work or batches of coordinated changes. Prefer **GPT-6.2 Astra** for more complex problems, even when the resulting diff is small.
