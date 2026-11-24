"""Generate a WAV, then play through the user's Linux audio session."""
import logging
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path


class Speaker:
    def __init__(self, config):
        self.enabled = config.get('enabled', True)
        self.speed = str(config.get('speed', 165))
        self.voice = str(config.get('voice', 'en-us'))
        self.player = config.get('player', 'auto')
        self.target = config.get('target')

    def speak(self, text, dismissed=None):
        if dismissed is not None and dismissed.is_set():
            return True
        if not self.enabled:
            print('[MOCK SPEECH]', text)
            return None  # explicitly simulated, never reported as physical audio success
        try:
            executable = shutil.which('espeak-ng')
            choices = ['pw-play', 'paplay', 'aplay'] if self.player == 'auto' else [self.player]
            player = next((shutil.which(x) for x in choices if shutil.which(x)), None)
            if not executable or not player:
                raise RuntimeError('Install espeak-ng and an audio player')
            with tempfile.TemporaryDirectory(prefix='briefing-') as directory:
                wav = Path(directory) / 'speech.wav'
                subprocess.run([executable, '-s', self.speed, '-v', self.voice, '-w', str(wav), '--stdin'],
                               input=str(text), text=True, check=True, timeout=15, capture_output=True)
                with wave.open(str(wav), 'rb') as audio:
                    duration = audio.getnframes() / audio.getframerate()
                command = [player]
                if self.target:
                    if Path(player).name == 'pw-play': command += ['--target', str(self.target)]
                    elif Path(player).name == 'paplay': command += ['--device', str(self.target)]
                    else: raise RuntimeError('Explicit target requires pw-play or paplay')
                command.append(str(wav))
                timeout = max(60, duration + 15)
                if dismissed is None:
                    subprocess.run(command, check=True, timeout=timeout, capture_output=True)
                else:
                    self._play_until_dismissed(command, timeout, dismissed)
            return True
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            logging.warning('SPEECH_FAILURE=%s', type(error).__name__)
            print('[AUDIO FAILURE] Check Linux output and speaker connection.')
            return False

    def _play_until_dismissed(self, command, timeout, dismissed):
        if dismissed.is_set():
            return
        deadline = time.monotonic() + timeout
        with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as player:
            try:
                while player.poll() is None:
                    if dismissed.wait(.05):
                        return
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(command, timeout)
                if player.returncode and not dismissed.is_set():
                    raise subprocess.CalledProcessError(player.returncode, command)
            finally:
                if player.poll() is None:
                    player.terminate()
                    try:
                        player.wait(timeout=.5)
                    except subprocess.TimeoutExpired:
                        player.kill()
