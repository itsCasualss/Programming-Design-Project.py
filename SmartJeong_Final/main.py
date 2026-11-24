"""Member 3 owns the explicit state machine and subsystem integration."""
import argparse
from contextlib import nullcontext
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading
import time

from config import load_config
from display_interface import DisplayManager, TkDashboard
from gpio_control import StatusLED
from presenter import Presenter
from services import InformationServices, error_briefing
from speech_output import Speaker
from voice_interface import create_voice_interface, ScriptedVoiceInterface

BASE_DIR = Path(__file__).resolve().parent
TRANSITIONS = {
    'startup': {'idle', 'error'}, 'idle': {'prompt', 'error'},
    'prompt': {'listening', 'error'}, 'listening': {'processing', 'error', 'idle'},
    'processing': {'output', 'error'}, 'output': {'idle', 'error'}, 'error': {'idle'},
}


class BriefingBox:
    def __init__(self, config=None, display=None, led=None, speaker=None, voice=None, services=None, stop=None):
        self.config = config or load_config()
        self.stop = stop or threading.Event()
        self.result_dismissed = threading.Event()
        self.display = display or DisplayManager(self.config['display'], self.stop)
        self.status_led = led or StatusLED(self.config['gpio'])
        self.speaker = speaker or Speaker(self.config['speech'])
        self.voice = voice or create_voice_interface(self.config['voice'], self.stop, self.display.tick)
        self.services = services or InformationServices(self.config)
        self.presenter = Presenter(self.display, self.speaker, hold_seconds=0 if hasattr(self.voice, 'wait_after_result') else self.config.get('response_seconds', 60))
        self.state, self.history = 'startup', ['startup']
        self.failed = False

    def set_state(self, state):
        if state not in TRANSITIONS.get(self.state, set()):
            raise ValueError(f'Illegal transition {self.state} -> {state}')
        self.state = state
        self.history.append(state)
        self.history = self.history[-100:]  # bounded diagnostic history
        logging.info('STATE=%s', state)
        self.status_led.set_state(state)

    def error(self, message):
        if self.state != 'error': self.set_state('error')
        self.display.show_error(message)
        self.speaker.speak(message)
        self.display.hold(self.config.get('hold_seconds', 3))

    def cycle(self):
        """One complete interaction, including recovery back to idle."""
        if self.state == 'startup': self.set_state('idle')
        self.display.show_idle()
        try:
            with getattr(self.voice, 'command_capture', nullcontext)():
                if not self.voice.wait_for_wake() or self.stop.is_set(): return
                self.set_state('prompt')
                self.display.show_menu()
                if self.speaker.speak('Pwincess Jeong, what would you like me to assist you with?') is False:
                    self.error('Audio output unavailable. Check the speaker connection.')
                    return
                # Bluetooth output may have a short hardware tail after playback exits.
                self.stop.wait(self.config.get('speech', {}).get('settle_seconds', .25))
                self.set_state('listening')
                self.display.show_listening()
                command = self.voice.listen_for_command(self.config['voice'].get('command_timeout_seconds', 8))
            if self.stop.is_set() or command == 'return home': return
            if command not in ('schedule', 'pills', 'weather', 'news'):
                self.error("I didn't understand. Please try again.")
                return
            self.set_state('processing')
            self.display.show_processing(command)
            if command == 'news' and hasattr(self.display, 'choose_news'):
                from news_search import fetch_news
                choice = self.display.choose_news()
                if choice is None: return
                self.display.show_processing('news')
                try: briefing = fetch_news(self.services, choice)
                except Exception as error:
                    self.error('News search unavailable. Check your connection or try broader keywords.')
                    return
            else:
                briefing = self.services.dispatch(command)
            if not briefing['ok']:
                self.error(briefing['speech'])
                return
            self.result_dismissed.clear()
            self.set_state('output')
            if self.presenter.present(briefing, self.result_dismissed) is False:
                self.set_state('error')
            if hasattr(self.voice, 'wait_after_result'):
                self.voice.wait_after_result(self.config.get('response_seconds', 60), self.result_dismissed)
        except (KeyboardInterrupt, EOFError):
            if self.state == 'listening':
                self.set_state('error')
            raise
        except Exception as error:
            logging.warning('INTERACTION_FAILURE=%s', type(error).__name__)
            self.error('A subsystem is unavailable. Check setup and try again.')
            self.stop.wait(2)  # prevents a broken microphone causing a busy retry loop
        finally:
            if self.state not in ('idle', 'startup'):
                if 'idle' not in TRANSITIONS[self.state]:
                    self.set_state('error')  # interrupted operation, no extra speech
                self.set_state('idle')
                self.display.show_idle()

    def run(self):
        try:
            self.display.show_startup()
            if hasattr(self.voice, 'prepare'):
                self.voice.prepare()  # model/device failure is visible before claiming idle readiness
            while not self.stop.is_set(): self.cycle()
        except (KeyboardInterrupt, EOFError):
            pass
        except Exception as error:
            self.failed = True
            logging.error('STARTUP_FAILURE=%s', type(error).__name__)
            self.error('Startup failed. Check models, microphone, and configuration.')
        finally:
            self.stop.set()
            self.status_led.close()
            self.display.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='SmartJeong')
    parser.add_argument('--demo', action='store_true', help='Scripted offline software demonstration')
    parser.add_argument('--hardware', action='store_true', help='Keep hardware enabled during scripted demo')
    parser.add_argument('--offline', action='store_true', help='Use labeled synthetic weather/news fixtures')
    parser.add_argument('--voice', action='store_true', help='Require real wake word and microphone')
    parser.add_argument('--tk', action='store_true', help='Open the Member 3 Tkinter dashboard')
    parser.add_argument('--no-audio', action='store_true', help='Explicitly skip speaker output during bring-up')
    parser.add_argument('--hdmi', action='store_true', help='Fullscreen HDMI dashboard; disable SPI display')
    parser.add_argument('--dual', action='store_true', help='Fullscreen HDMI and required TFT together')
    parser.add_argument('--dsi', action='store_true', help='Fullscreen desktop dashboard on the DSI screen; disable legacy SPI display')
    args = parser.parse_args(argv)
    if args.dsi and args.dual: parser.error('--dsi and --dual select different display modes')
    if args.dsi: args.hdmi = True
    if args.hdmi or args.dual: args.tk = True
    config = load_config()
    if args.demo and args.voice: parser.error('--demo uses scripted input; use --voice --offline for real voice with fixtures')
    if args.hardware and not args.demo: parser.error('--hardware is only needed with --demo')
    config['offline'] = args.demo or args.offline
    if args.no_audio: config['speech']['enabled'] = False
    if args.hardware:
        config['display']['required'] = True
        config['gpio']['required'] = True
    if args.voice: config['voice']['input_mode'] = 'voice'
    if args.demo and not args.hardware:
        for part in ('display', 'gpio', 'speech'): config[part]['enabled'] = False
        config['hold_seconds'] = 0
        config['response_seconds'] = 0
        config['speech']['settle_seconds'] = 0
    if args.demo and args.tk:
        config['hold_seconds'] = 2
        config['response_seconds'] = 2
    if args.hdmi:
        config['display']['enabled'] = False
        config['display']['required'] = False
        config['display']['fullscreen'] = True
    if args.dual:
        config['display'].update(enabled=True, required=True, fullscreen=True)
    if args.tk: config['voice']['exit_on_eof'] = False
    config['display']['input_mode'] = config['voice'].get('input_mode', 'keyboard')
    logs = BASE_DIR / 'logs'
    logs.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[RotatingFileHandler(logs / 'briefing_box.log', maxBytes=100000, backupCount=2)])
    voice = ScriptedVoiceInterface(['schedule', 'pills', 'weather', 'news', None]) if args.demo else None
    box = BriefingBox(config, voice=voice)
    if args.tk:
        try: dashboard = TkDashboard(box.display, box.stop, box)
        except Exception:
            box.status_led.close()
            box.display.close()
            raise
        worker = threading.Thread(target=box.run, daemon=True)
        worker.start()
        try: dashboard.run()
        finally:
            box.stop.set()
            worker.join(timeout=1)
    else:
        box.run()
    return 1 if box.failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
