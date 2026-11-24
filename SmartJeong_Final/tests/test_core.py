"""Offline regression tests: failures, timing boundaries, and integration contracts."""
import copy
from datetime import datetime
import io
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import load_config
from display_interface import DisplayManager, wrap_pages
from gpio_control import StatusLED
from main import BriefingBox
from presenter import format_briefing
from services import InformationServices, error_briefing
from speech_output import Speaker
from voice_interface import PiVoiceInterface, ScriptedVoiceInterface, COMMAND_MAP


class FakeDisplay:
    def __init__(self): self.calls = []
    def __getattr__(self, name):
        return lambda *args: self.calls.append((name, args))


class FakeLED:
    def __init__(self): self.states = []
    def set_state(self, state): self.states.append(state)
    def close(self): pass


class FakeSpeaker:
    def __init__(self, success=True): self.texts, self.success = [], success
    def speak(self, text):
        self.texts.append(text)
        return self.success


class Tests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.config['offline'] = True
        self.config['hold_seconds'] = 0
        self.config['speech']['settle_seconds'] = 0
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.zone = ZoneInfo('America/New_York')
        self.now = datetime(2026, 10, 19, 12, 55, tzinfo=self.zone)
        self.service = InformationServices(self.config, now=lambda: self.now)
        self.stdout = patch('sys.stdout', new_callable=io.StringIO)
        self.stdout.start()
        self.addCleanup(self.stdout.stop)

    def file(self, name, text):
        path = Path(self.temp.name) / name
        path.write_text(text)
        return str(path)

    def box(self, command='weather', services=None, speaker=None):
        return BriefingBox(self.config, FakeDisplay(), FakeLED(), speaker or FakeSpeaker(),
                           ScriptedVoiceInterface([command]), services or self.service)

    def test_all_four_services(self):
        for command in ('schedule', 'pills', 'weather', 'news'):
            with self.subTest(command=command):
                value = self.service.dispatch(command)
                self.assertTrue(value['ok'])
                rendered = format_briefing(value)
                self.assertTrue(rendered['speech'])
                self.assertTrue(rendered['display'])
                self.assertIn('DEMO', rendered['title'])

    def test_calendar_recurs_on_future_demo_day(self):
        self.now = datetime(2027, 5, 10, 23, 0, tzinfo=self.zone)
        value = self.service.dispatch('schedule')
        self.assertEqual(value['data']['total'], 3)
        self.assertEqual([x['time'] for x in value['data']['events']], ['9:00 AM', '1:00 PM', '3:30 PM'])

    def test_calendar_timezone_all_day_cancelled_and_sort(self):
        content = '''BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:late
DTSTART:20261019T220000Z
SUMMARY:Late
END:VEVENT
BEGIN:VEVENT
UID:early
DTSTART:20261019T130000Z
SUMMARY:Early
END:VEVENT
BEGIN:VEVENT
UID:all
DTSTART;VALUE=DATE:20261019
DTEND;VALUE=DATE:20261020
SUMMARY:All-day
END:VEVENT
BEGIN:VEVENT
UID:cancelled
DTSTART:20261019T140000Z
SUMMARY:Cancelled
STATUS:CANCELLED
END:VEVENT
END:VCALENDAR'''
        self.config['schedule']['local_file'] = self.file('calendar.ics', content)
        data = self.service.dispatch('schedule')['data']
        self.assertEqual([x['summary'] for x in data['events']], ['All-day', 'Early', 'Late'])
        self.assertEqual(data['events'][1]['time'], '9:00 AM')

    def test_empty_calendar(self):
        self.config['schedule']['local_file'] = self.file('empty.ics', 'BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR')
        value = self.service.dispatch('schedule')
        self.assertTrue(value['ok'])
        self.assertIn('No events', format_briefing(value)['speech'])

    def test_missing_calendar(self):
        self.config['schedule']['local_file'] = 'not_present.ics'
        self.assertFalse(self.service.dispatch('schedule')['ok'])

    def test_malformed_calendar(self):
        self.config['schedule']['local_file'] = self.file('bad.ics', 'not a calendar')
        self.assertFalse(self.service.dispatch('schedule')['ok'])

    def test_invalid_event(self):
        self.config['schedule']['local_file'] = self.file('bad.ics', 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x\nSUMMARY:X\nEND:VEVENT\nEND:VCALENDAR')
        self.assertFalse(self.service.dispatch('schedule')['ok'])

    def test_private_feed_in_offline_mode_does_not_connect(self):
        self.config['schedule']['ics_url'] = 'https://example.org/private'
        self.service.fetch = lambda *args: self.fail('network accessed')
        self.assertFalse(self.service.dispatch('schedule')['ok'])

    def test_private_feed_success(self):
        self.config['offline'] = False
        self.config['schedule']['ics_url'] = 'https://example.org/private'
        self.service.fetch = lambda *args: (ROOT / 'data/calendar.ics').read_bytes()
        value = self.service.dispatch('schedule')
        self.assertTrue(value['ok'])
        self.assertFalse(value['demo'])

    def test_pills_next(self):
        item = self.service.dispatch('pills')['data']['items'][0]
        self.assertEqual(item, {'name': 'Demo Item B', 'time': '1:00 PM', 'day': 'Today'})

    def test_pills_same_minute(self):
        self.now = self.now.replace(hour=13, minute=0, second=55)
        self.assertEqual(self.service.dispatch('pills')['data']['items'][0]['day'], 'Today')

    def test_pills_past_not_called_due(self):
        self.now = self.now.replace(hour=13, minute=1)
        rendered = format_briefing(self.service.dispatch('pills'))
        self.assertNotIn('due', rendered['speech'])
        self.assertIn('unknown', rendered['display'])

    def test_pills_midnight_rollover(self):
        self.now = self.now.replace(hour=23, minute=59)
        items = self.service.dispatch('pills')['data']['items']
        self.assertTrue(all(x['day'] == 'Tomorrow' for x in items))
        self.assertEqual(items[0]['time'], '8:00 AM')

    def test_empty_pills(self):
        self.config['pills']['file'] = self.file('pills.json', '[]')
        self.assertIn('No reminders', format_briefing(self.service.dispatch('pills'))['speech'])

    def test_invalid_pills(self):
        for raw in ['{}', 'not json', '[{"name":"A","times":["25:99"]}]', '[{"name":"A","times":"08:00"}]', '[{"times":["08:00"]}]']:
            with self.subTest(raw=raw):
                self.config['pills']['file'] = self.file('pills.json', raw)
                self.assertFalse(self.service.dispatch('pills')['ok'])

    def test_network_failure_for_each_remote_service(self):
        self.config['offline'] = False
        self.config['schedule']['ics_url'] = 'https://example.org/secret'
        def fail(*args): raise TimeoutError('secret URL')
        self.service.fetch = fail
        for command in ('schedule', 'weather', 'news'):
            with self.subTest(command=command), self.assertLogs(level='WARNING') as logs:
                value = self.service.dispatch(command)
                self.assertFalse(value['ok'])
                self.assertNotIn('secret', ' '.join(logs.output))

    def test_weather_malformed_numbers(self):
        self.config['offline'] = False
        raw = json.loads((ROOT / 'data/weather.json').read_text())
        raw['current']['temperature_2m'] = 'nan'
        self.service.fetch = lambda *args: json.dumps(raw).encode()
        self.assertFalse(self.service.dispatch('weather')['ok'])

    def test_news_empty_and_malformed(self):
        self.config['offline'] = False
        for raw in (b'not xml', b'<rss version="2.0"><channel></channel></rss>'):
            self.service.fetch = lambda *args: raw
            self.assertFalse(self.service.dispatch('news')['ok'])

    def test_unknown_dispatch(self):
        self.assertFalse(self.service.dispatch('shopping')['ok'])

    def test_exact_success_state_sequence(self):
        box = self.box()
        box.cycle()
        self.assertEqual(box.history, ['startup', 'idle', 'prompt', 'listening', 'processing', 'output', 'idle'])
        self.assertEqual(len(box.speaker.texts), 2)

    def test_unrecognized_state_sequence(self):
        box = self.box(None)
        box.cycle()
        self.assertEqual(box.history, ['startup', 'idle', 'prompt', 'listening', 'error', 'idle'])

    def test_service_failure_returns_idle(self):
        self.config['schedule']['local_file'] = 'absent'
        box = self.box('schedule')
        box.cycle()
        self.assertEqual(box.history[-3:], ['processing', 'error', 'idle'])

    def test_audio_failure_stops_before_listening(self):
        box = self.box(speaker=FakeSpeaker(False))
        box.cycle()
        self.assertEqual(box.history[-3:], ['prompt', 'error', 'idle'])
        self.assertNotIn('listening', box.history)

    def test_illegal_transition_rejected(self):
        box = self.box()
        with self.assertRaises(ValueError): box.set_state('output')

    def test_run_cleanup(self):
        box = self.box()
        box.run()
        self.assertTrue(box.stop.is_set())
        self.assertTrue(any(x[0] == 'close' for x in box.display.calls))

    def test_display_pages_preserve_words_and_bounds(self):
        text = 'A deliberately long headline plus other words to exercise four lines per display page. ' * 5
        pages = wrap_pages(text)
        self.assertGreater(len(pages), 1)
        self.assertTrue(all(len(page) <= 4 for page in pages))
        self.assertTrue(all(len(line) <= 20 for page in pages for line in page))
        self.assertEqual(' '.join(' '.join(page) for page in pages).split(), text.split())

    def test_display_handles_long_token_unicode_and_empty(self):
        for text in ('x' * 200, 'Tampa café ☀', ''):
            self.assertTrue(all(len(line) <= 20 for page in wrap_pages(text) for line in page))

    def test_display_runtime_disconnect(self):
        display = DisplayManager({'enabled': False})
        display.device = object()
        display.canvas = lambda device: (_ for _ in ()).throw(OSError())
        display.show_result('Test', 'Body')
        self.assertIsNone(display.device)
        self.assertIn('Display write failed', display.body)

    def test_gpio_runtime_disconnect(self):
        led = StatusLED({'enabled': False})
        class Broken:
            def off(self): raise OSError()
            def close(self): pass
        led.led = Broken()
        led.set_state('listening')
        self.assertIsNone(led.led)

    def test_speech_missing_binary_reports_failure(self):
        with patch('speech_output.shutil.which', return_value=None):
            self.assertFalse(Speaker({'enabled': True}).speak('test'))

    def test_mock_speech_not_hardware_success(self):
        self.assertIsNone(Speaker({'enabled': False}).speak('test'))

    def test_audio_callback_bounded(self):
        q = queue.Queue(maxsize=1)
        callback = PiVoiceInterface._make_callback(q)
        callback(b'a', 1, None, None)
        callback(b'b', 1, None, None)
        self.assertEqual(q.qsize(), 1)

    def test_interrupt_during_prompt_recovers_without_illegal_transition(self):
        speaker = FakeSpeaker()
        def interrupt(text): raise KeyboardInterrupt
        speaker.speak = interrupt
        box = self.box(speaker=speaker)
        with self.assertRaises(KeyboardInterrupt): box.cycle()
        self.assertEqual(box.history[-3:], ['prompt', 'error', 'idle'])

    def test_interrupt_during_listening_recovers(self):
        box = self.box()
        def interrupt(timeout): raise KeyboardInterrupt
        box.voice.listen_for_command = interrupt
        with self.assertRaises(KeyboardInterrupt): box.cycle()
        self.assertEqual(box.history[-3:], ['listening', 'error', 'idle'])

    def test_stop_during_listening_recovers(self):
        box = self.box()
        def cancel(timeout):
            box.stop.set()
            return None
        box.voice.listen_for_command = cancel
        box.cycle()
        self.assertEqual(box.state, 'idle')

    def test_live_weather_valid_schema(self):
        self.config['offline'] = False
        self.service.fetch = lambda *args: (ROOT / 'data/weather.json').read_bytes()
        value = self.service.dispatch('weather')
        self.assertTrue(value['ok'])
        self.assertFalse(value['demo'])
        self.assertEqual(value['data']['temperature'], 82)

    def test_live_news_valid_schema(self):
        self.config['offline'] = False
        self.service.fetch = lambda *args: (ROOT / 'data/news.xml').read_bytes()
        value = self.service.dispatch('news')
        self.assertTrue(value['ok'])
        self.assertFalse(value['demo'])
        self.assertEqual(len(value['data']['headlines']), 3)

    def test_no_open_ended_command_mapping(self):
        self.assertNotIn('tell me the weather please', COMMAND_MAP)
        self.assertEqual(COMMAND_MAP['four'], 'news')


if __name__ == '__main__': unittest.main()
