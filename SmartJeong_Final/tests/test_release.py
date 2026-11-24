import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import Mock, patch
from tempfile import TemporaryDirectory
import json
from austin_adapter import load_recognizer
from setup_personal import validate_times, private_write
from services import InformationServices
from config import load_config
from presenter import format_briefing

class ReleaseTests(unittest.TestCase):
    def test_austin_parser_and_isolated_import(self):
        sentinel=object()
        with patch.dict(sys.modules,{'numpy':Mock(),'vosk':Mock(),'sounddevice':Mock(),'audio_input':sentinel}):
            recognition=load_recognizer()
            self.assertIs(sys.modules['audio_input'],sentinel)
            for text,expected in [('my schedule','schedule'),('medication','pills'),('option three','weather'),('4','news'),('weather and news',None),('hello',None)]:
                self.assertEqual(recognition.parse_command(text),expected)

    def test_reminder_setup_validation_and_private_write(self):
        self.assertEqual(validate_times('20:00,08:00,08:00'),['08:00','20:00'])
        for bad in ['24:00','8:00','','09:60']:
            with self.assertRaises(ValueError):validate_times(bad)
        with TemporaryDirectory() as directory:
            path=Path(directory)/'config.local.json'
            private_write(path,'{}')
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(json.loads(path.read_text()),{})

    def test_personal_reminders_not_labeled_fictional(self):
        config=load_config();config['pills']['demo']=False
        briefing=InformationServices(config).pills()
        self.assertFalse(briefing['demo'])
        rendered=format_briefing(briefing)
        self.assertNotIn('fictional',rendered['speech'])
        self.assertNotIn('DEMO',rendered['title'])

if __name__=='__main__':unittest.main()
