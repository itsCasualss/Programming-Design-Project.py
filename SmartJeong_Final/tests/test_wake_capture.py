"""Regression tests for a service name spoken during the wake greeting."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from austin_adapter import AustinVoiceInterface, load_recognizer
from config import load_config
from main import BriefingBox
from voice_interface import PiVoiceInterface


class TestWakeCapture(unittest.TestCase):
    def test_first_service_name_reaches_news_dialog(self):
        import numpy as np

        wake_frame = b'ww'
        prompt_frame = b'pp'
        command_frame = b'nn'

        class Recognizer:
            def __init__(self, model, rate, grammar):
                self.grammar = json.loads(grammar)

            def AcceptWaveform(self, raw):
                if raw == wake_frame:
                    raise AssertionError('Wake audio was sent to the command recognizer.')
                self.text = {prompt_frame: 'what would you like me to assist you with',
                             command_frame: 'news'}[raw]
                return True

            def Result(self):
                return json.dumps({'text': self.text})

            def FinalResult(self):
                return '{}'

        for backend in (PiVoiceInterface, AustinVoiceInterface):
            with self.subTest(backend=backend.__name__):
                config = load_config()
                config['speech']['settle_seconds'] = 0
                config['voice']['command_timeout_seconds'] = .1
                config['hold_seconds'] = 0
                states = []
                streams = []
                active = []
                dialog_calls = []

                voice = backend(config['voice'])
                def predict(raw):
                    self.assertEqual(raw.dtype, np.int16)
                    return {'hey_jarvis': 1}

                voice.oww = SimpleNamespace(reset=lambda: None, predict=predict)
                voice.vosk = object()

                @contextmanager
                def stream(audio):
                    streams.append(audio)
                    active.append(audio)
                    audio.put_nowait(wake_frame)
                    try:
                        yield
                    finally:
                        active.pop()

                def speak(prompt):
                    if prompt.startswith('Pwincess Jeong'):
                        self.assertEqual(len(active), 1)
                        active[0].put_nowait(prompt_frame)
                        active[0].put_nowait(command_frame)
                    return True

                def choose_news():
                    self.assertFalse(active)
                    dialog_calls.append(True)
                    return None

                voice._stream = stream
                display = SimpleNamespace(show_idle=lambda: None, show_menu=lambda: None,
                                          show_listening=lambda: None, show_processing=lambda command: None,
                                          choose_news=choose_news, show_error=self.fail)
                led = SimpleNamespace(set_state=states.append)
                box = BriefingBox(config, display, led, SimpleNamespace(speak=speak), voice)
                with patch.dict(sys.modules, {'vosk': SimpleNamespace(KaldiRecognizer=Recognizer, Model=object),
                                              'sounddevice': SimpleNamespace()}):
                    if isinstance(voice, AustinVoiceInterface):
                        voice.recognition = load_recognizer()
                    box.cycle()

                self.assertEqual(dialog_calls, [True])
                self.assertEqual(len(streams), 1)
                self.assertFalse(active)
                self.assertEqual(states, ['idle', 'prompt', 'listening', 'processing', 'error', 'idle'])
