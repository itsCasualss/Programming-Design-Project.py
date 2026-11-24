"""Bounded local recognition; never silently downgrade a real voice demonstration."""
import json
import logging
import queue
import select
import sys
import threading
import time
from contextlib import closing, contextmanager, nullcontext
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COMMAND_MAP = {'schedule': 'schedule', 'one': 'schedule', '1': 'schedule',
               'pills': 'pills', 'two': 'pills', '2': 'pills',
               'weather': 'weather', 'three': 'weather', '3': 'weather',
               'news': 'news', 'four': 'news', '4': 'news'}


class KeyboardVoiceInterface:
    def __init__(self, stop=None, tick=None, exit_on_eof=True):
        self.stop, self.tick = stop or threading.Event(), tick or (lambda: None)
        self.exit_on_eof = exit_on_eof
        self.pending = None
        self.lines = queue.Queue()
        # One reader avoids mixing select() with Python's buffered stdin.
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        for line in sys.stdin:
            self.lines.put(line.strip().lower())
        if self.exit_on_eof: self.lines.put(None)

    def _read(self, prompt, timeout=None, dismissed=None):
        print(prompt, flush=True)
        deadline = time.monotonic() + timeout if timeout is not None else float('inf')
        while not self.stop.is_set() and time.monotonic() < deadline:
            if dismissed is not None and dismissed.is_set():
                return None
            self.tick()
            try: line = self.lines.get(timeout=.1)
            except queue.Empty: continue
            if line is None or line == 'q': raise KeyboardInterrupt
            return line
        return None

    def wait_for_wake(self):
        line = self._read('Type schedule / pills / weather / news, or ENTER for menu; q quits')
        self.pending = line if line else None
        return line is not None

    def listen_for_command(self, timeout_seconds=8):
        if self.pending is not None:
            line, self.pending = self.pending, None
        else:
            line = self._read('Schedule / Pills / Weather / News (waiting for your choice):')
            while line == '':
                line = self._read('Type a service name:')
        return line if line == 'return home' else COMMAND_MAP.get(line)

    def wait_after_result(self, seconds=60, dismissed=None):
        # Discard queued key repeats before starting the response interval.
        while not self.lines.empty():
            try:
                queued = self.lines.get_nowait()
                if queued is None or queued == 'q': raise KeyboardInterrupt
            except queue.Empty: break
        self._read('Press ENTER to return home or q to quit.', seconds, dismissed)


class ScriptedVoiceInterface:
    def __init__(self, commands): self.commands = iter(commands)
    def wait_for_wake(self):
        try: self.command = next(self.commands)
        except StopIteration: raise KeyboardInterrupt
        return True
    def listen_for_command(self, timeout_seconds=8): return self.command


class PiVoiceInterface:
    def __init__(self, config, stop=None, tick=None):
        self.config = config
        self.stop, self.tick = stop or threading.Event(), tick or (lambda: None)
        self.sample_rate = 16000
        self.result_listening = threading.Event()
        self.touch_actions = queue.Queue(maxsize=1)
        self.audio_device = config.get('audio_device')
        self.wakeword_name = config.get('wakeword_name', 'hey_jarvis')
        self.threshold = float(config.get('wakeword_threshold', .5))
        self.vosk_path = BASE_DIR / config.get('vosk_model_path', 'models/vosk-model-small-en-us-0.15')
        self.oww, self.vosk = None, None

    def prepare(self):
        import sounddevice as sd
        from openwakeword.model import Model as WakeModel
        from vosk import Model, SetLogLevel
        if not self.vosk_path.is_dir():
            raise RuntimeError('Run setup_models.py before voice mode')
        sd.check_input_settings(device=self.audio_device, channels=1, dtype='int16', samplerate=16000)
        self.oww = WakeModel(wakeword_models=[self.wakeword_name], inference_framework='onnx')
        SetLogLevel(-1)
        self.vosk = Model(str(self.vosk_path))

    @staticmethod
    def _make_callback(audio_queue):
        def callback(indata, frames, time_info, status):
            # Never block PortAudio. A bounded queue prevents unbounded RAM growth.
            try: audio_queue.put_nowait(bytes(indata))
            except queue.Full: pass
        return callback

    def _stream(self, q):
        import sounddevice as sd
        return sd.RawInputStream(samplerate=16000, blocksize=1280, device=self.audio_device,
                                 dtype='int16', channels=1, callback=self._make_callback(q))

    def submit_touch(self, value):
        """Pass one dashboard action to the worker that owns the interaction."""
        try:
            self.touch_actions.put_nowait(value)
        except queue.Full:
            pass

    def _next_touch_action(self):
        try:
            return self.touch_actions.get_nowait()
        except queue.Empty:
            return None

    @contextmanager
    def command_capture(self):
        if self.vosk is None or self.oww is None:
            self.prepare()
        # 192 x 80 ms leaves room to capture speech during the greeting and speaker tail.
        audio = queue.Queue(maxsize=192)
        with self._stream(audio):
            self._command_audio = audio
            try:
                yield
            finally:
                self._command_audio = None

    def wait_for_wake(self):
        import numpy as np
        capture = nullcontext() if getattr(self, '_command_audio', None) is not None else self.command_capture()
        with capture:
            self.oww.reset()
            last_audio = time.monotonic()
            while not self.stop.is_set():
                if self._next_touch_action() == '':
                    return True
                self.tick()
                try: raw = self._command_audio.get(timeout=.1)
                except queue.Empty:
                    if time.monotonic() - last_audio > 3:
                        raise RuntimeError('Microphone stopped delivering audio')
                    continue
                last_audio = time.monotonic()
                scores = self.oww.predict(np.frombuffer(raw, dtype=np.int16))
                if any(float(score) >= self.threshold for score in scores.values()):
                    return True
        return False

    def _command_grammar(self):
        return ['schedule', 'pills', 'weather', 'news', 'one', 'two', 'three', 'four']

    def _parse_command(self, text):
        return COMMAND_MAP.get(text)

    def listen_for_command(self, timeout_seconds=8):
        from vosk import KaldiRecognizer
        if self.stop.is_set():
            return None
        capture = nullcontext() if getattr(self, '_command_audio', None) is not None else self.command_capture()
        with capture:
            # Let the decoder distinguish the audible prompt from menu options.
            grammar = [*self._command_grammar(), 'what would you like me to assist you with', '[unk]']
            recognizer = KaldiRecognizer(self.vosk, 16000, json.dumps(grammar))
            deadline = time.monotonic() + timeout_seconds
            while not self.stop.is_set():
                action = self._next_touch_action()
                if action == 'return home':
                    return action
                if action in COMMAND_MAP:
                    return COMMAND_MAP[action]
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.tick()
                try: raw = self._command_audio.get(timeout=min(.1, remaining))
                except queue.Empty: continue
                if recognizer.AcceptWaveform(raw):
                    text = json.loads(recognizer.Result()).get('text', '').strip().lower()
                    command = self._parse_command(text)
                    if command is not None:
                        print('Recognized:', text)
                        return command
            if self.stop.is_set():
                return None
            final = json.loads(recognizer.FinalResult()).get('text', '').strip().lower()
            return self._parse_command(final)

    def listen_for_news(self, finished, seconds=12):
        """Return a free-form utterance, or None if the dialog was dismissed."""
        if finished.is_set() or self.stop.is_set():
            return None

        from vosk import KaldiRecognizer

        recognizer = KaldiRecognizer(self.vosk, self.sample_rate)
        with closing(self._voice_frames(seconds, finished)) as frames:
            for frame in frames:
                if recognizer.AcceptWaveform(frame):
                    words = json.loads(recognizer.Result()).get('text', '').strip()
                    if words:
                        return words
        if not (finished.is_set() or self.stop.is_set()):
            return json.loads(recognizer.FinalResult()).get('text', '').strip() or None
        return None

    def wait_after_result(self, seconds=60, dismissed=None):
        """Listen for dismissal after the briefing finishes speaking."""
        if seconds <= 0 or self.stop.is_set() or (dismissed is not None and dismissed.is_set()):
            return

        from vosk import KaldiRecognizer

        dismiss_words = ('return home', 'home', 'return')
        grammar = json.dumps([*dismiss_words, '[unk]'])
        recognizer = KaldiRecognizer(self.vosk, self.sample_rate, grammar)
        partial_command = None
        partial_since = 0.0
        self.result_listening.set()
        try:
            with closing(self._voice_frames(seconds, dismissed)) as frames:
                for frame in frames:
                    if recognizer.AcceptWaveform(frame):
                        command = json.loads(recognizer.Result()).get('text', '').strip().lower()
                        if command in dismiss_words:
                            logging.info('RESULT_DISMISSED_BY_VOICE')
                            return
                        partial_command = None
                        continue

                    partial = json.loads(recognizer.PartialResult()).get('partial', '').strip().lower()
                    now = time.monotonic()
                    if partial not in dismiss_words:
                        partial_command = None
                    elif partial != partial_command:
                        partial_command, partial_since = partial, now
                    elif now - partial_since >= .25:
                        logging.info('RESULT_DISMISSED_BY_VOICE')
                        return
        finally:
            self.result_listening.clear()

    def _voice_frames(self, seconds, finished):
        audio = queue.Queue(maxsize=32)
        deadline = time.monotonic() + seconds
        with self._stream(audio):
            while not self.stop.is_set():
                if finished is not None and finished.is_set():
                    return
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                self.tick()
                try:
                    frame = audio.get(timeout=min(.1, remaining))
                except queue.Empty:
                    continue
                if finished is None or not finished.is_set():
                    yield frame


def create_voice_interface(config, stop=None, tick=None):
    if config.get('input_mode', 'keyboard') == 'voice':
        if config.get('command_backend', 'austin') == 'austin':
            from austin_adapter import AustinVoiceInterface
            return AustinVoiceInterface(config, stop, tick)
        return PiVoiceInterface(config, stop, tick)
    return KeyboardVoiceInterface(stop, tick, config.get('exit_on_eof', True))
