from contextlib import nullcontext
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import numpy

from config import load_config
from dashboard import TkDashboard
from main import BriefingBox
from voice_interface import PiVoiceInterface


class TouchHomeTests(unittest.TestCase):
    def test_touch_wake_select_and_return_in_voice_mode(self):
        self.assertEqual(self.run_interaction('weather'),
                         ['startup', 'idle', 'prompt', 'listening', 'processing', 'output', 'idle'])

    def test_touch_return_in_voice_menu_skips_error(self):
        self.assertEqual(self.run_interaction('return home'),
                         ['startup', 'idle', 'prompt', 'listening', 'idle'])

    def test_spoken_wake_accepts_a_touch_selection(self):
        self.assertEqual(self.run_interaction('weather', spoken_wake=True),
                         ['startup', 'idle', 'prompt', 'listening', 'processing', 'output', 'idle'])

    def run_interaction(self, action, spoken_wake=False):
        config = load_config()
        config['offline'] = True
        config['speech']['settle_seconds'] = 0
        config['voice']['command_timeout_seconds'] = .2
        voice = PiVoiceInterface(config['voice'])
        def predict(audio):
            self.assertEqual(audio.dtype, numpy.int16)
            return {'hey_jarvis': 1}

        voice.oww = SimpleNamespace(reset=lambda: None, predict=predict)
        voice.vosk = object()
        def open_stream(audio):
            if spoken_wake:
                audio.put_nowait(b'\x00\x00')
            return nullcontext()

        voice._stream = Mock(side_effect=open_stream)
        dashboard = TkDashboard.__new__(TkDashboard)
        dashboard.modal = dashboard.background = dashboard.active_service = None
        dashboard.canvas = Mock()
        dashboard.width, dashboard.height, dashboard.fade = 800, 480, 1
        dashboard.body, dashboard.scroll = Mock(), Mock()
        dashboard.title = ''
        awakened = False

        def tap(*labels):
            dashboard.canvas.create_text.reset_mock()
            dashboard.draw()
            for call in dashboard.canvas.create_text.call_args_list:
                if call.kwargs.get('text') in labels:
                    x, y = call.args
                    dashboard.click(SimpleNamespace(x=x + 2, y=y + 2))
                    return
            self.fail(f'Expected dashboard control {labels}')

        def show_idle():
            nonlocal awakened
            dashboard.state_name = 'idle'
            if not awakened and not spoken_wake:
                tap('Wake / Return home')
                awakened = True

        def show_listening():
            dashboard.state_name = 'listening'
            tap('Wake / Return home' if action == 'return home' else 'Weather')

        def show_result(title, body):
            self.assertEqual(title, 'DEMO Weather')
            dashboard.state_name = 'output'
            tap('Return home', 'Wake / Return home')
            self.assertTrue(box.result_dismissed.is_set())

        display = SimpleNamespace(
            config={'input_mode': 'voice'}, zone=ZoneInfo('America/New_York'),
            show_idle=show_idle, show_menu=lambda: None, show_listening=show_listening,
            show_processing=Mock(), show_result=show_result, show_error=self.fail)
        box = BriefingBox(config, display, Mock(), SimpleNamespace(speak=lambda text: True), voice)
        dashboard.display, dashboard.box = display, box
        recognizer = Mock()
        recognizer.FinalResult.return_value = '{}'
        with patch.dict(sys.modules, {'vosk': SimpleNamespace(KaldiRecognizer=Mock(return_value=recognizer))}):
            box.cycle()

        self.assertEqual(voice._stream.call_count, 1)
        return box.history
