"""Integrate unchanged teammate recognition with our wake engine and config."""
import importlib.util
from pathlib import Path
import sys
from voice_interface import PiVoiceInterface

VENDOR = Path(__file__).resolve().parent / 'vendor/austin/voice_interface'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_recognizer():
    # Austin uses a bare audio_input import. Scope that alias to module loading.
    audio = load_module('_austin_audio', VENDOR / 'audio_input.py')
    previous = sys.modules.get('audio_input')
    sys.modules['audio_input'] = audio
    try:
        return load_module('_austin_recognition', VENDOR / 'speech_recognition.py')
    finally:
        if previous is None: sys.modules.pop('audio_input', None)
        else: sys.modules['audio_input'] = previous


class AustinVoiceInterface(PiVoiceInterface):
    def prepare(self):
        super().prepare()
        self.recognition = load_recognizer()

    def _command_grammar(self):
        phrases = [phrase for group in self.recognition.COMMANDS.values() for phrase in group]
        for number in self.recognition.OPTIONS:
            phrases.extend([
                number, f'option {number}', f'run option {number}', f'select option {number}', f'number {number}',
            ])
        return phrases

    def _parse_command(self, text):
        return self.recognition.parse_command(text)
