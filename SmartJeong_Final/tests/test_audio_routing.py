import unittest
from unittest.mock import patch
import wave
from speech_output import Speaker

class AudioRoutingTests(unittest.TestCase):
    def run_speech(self, player, target=None):
        calls=[]
        def run(args, **kwargs):
            calls.append(args)
            if '-w' in args:
                with wave.open(args[args.index('-w')+1], 'wb') as f:
                    f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
                    f.writeframes(b'\0\0'*160)
        with patch('speech_output.shutil.which', side_effect=lambda x:'/usr/bin/'+x), patch('speech_output.subprocess.run', side_effect=run):
            ok=Speaker({'player':player,'target':target}).speak('Pwincess Jeong')
        return ok,calls
    def test_pipewire_target(self):
        ok,calls=self.run_speech('pw-play','bluez_output.example')
        self.assertTrue(ok)
        self.assertEqual(calls[-1][1:3],['--target','bluez_output.example'])
    def test_pulse_target(self):
        ok,calls=self.run_speech('paplay','bluez_sink.example')
        self.assertTrue(ok)
        self.assertEqual(calls[-1][1:3],['--device','bluez_sink.example'])
    def test_default_output(self):
        ok,calls=self.run_speech('pw-play')
        self.assertTrue(ok);self.assertEqual(len(calls[-1]),2)
    def test_alsa_rejects_server_target(self):
        ok,calls=self.run_speech('aplay','bluez_output.example')
        self.assertFalse(ok);self.assertEqual(len(calls),1)
