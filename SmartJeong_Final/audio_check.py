"""Test the same TTS and output path used by SmartJeong."""
from config import load_config
from speech_output import Speaker

if __name__ == '__main__':
    ok = Speaker(load_config()['speech']).speak(
        'Pwincess Jeong, your SmartJeong speaker is ready for testing.')
    print('Playback process succeeded. Confirm the intended speaker was audible.'
          if ok else 'Playback failed or speech is disabled. Check audio configuration.')
    raise SystemExit(0 if ok else 1)
