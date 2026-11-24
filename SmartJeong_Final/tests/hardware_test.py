"""Physical bring-up helper. Human observations are required; mock output never passes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import load_config
from display_interface import DisplayManager
from gpio_control import StatusLED
from speech_output import Speaker


def main():
    config = load_config()
    config['display'].update(enabled=True, required=True)
    config['gpio'].update(enabled=True, required=True)
    display = led = None
    checks = []
    try:
        display = DisplayManager(config['display'])
        led = StatusLED(config['gpio'])
        display.show_result('HARDWARE TEST', 'Confirm readable text\nNo clipped edges')
        checks.append(input('OLED text readable? [y/N] ').lower() == 'y')
        led.set_state('processing')
        checks.append(input('LED blinking? [y/N] ').lower() == 'y')
        led.set_state('idle')
        checks.append(input('LED now off? [y/N] ').lower() == 'y')
        speaker = Speaker(dict(config['speech'], enabled=True))
        played = speaker.speak('Briefing Box audio output test.')
        checks.append(played is True and input('Heard the sentence from the intended speaker? [y/N] ').lower() == 'y')
        import sounddevice as sd
        print(sd.query_devices())
        sd.check_input_settings(device=config['voice'].get('audio_device'), channels=1, dtype='int16', samplerate=16000)
        print('Recording 2 seconds in memory. Speak near the USB microphone.')
        audio = sd.rec(32000, samplerate=16000, channels=1, dtype='int16', device=config['voice'].get('audio_device'))
        sd.wait()
        import numpy as np
        peak = int(np.max(np.abs(audio.astype(np.int32))))
        print('PCM peak:', peak, '(silence=0, clipping near 32767)')
        checks.append(peak > 0 and input('Correct USB microphone selected and signal plausible? [y/N] ').lower() == 'y')
        print('PASS' if all(checks) else 'INCOMPLETE: repair the failed hardware checks.')
        return 0 if all(checks) else 1
    finally:
        if led: led.close()
        if display: display.close()


if __name__ == '__main__': raise SystemExit(main())
