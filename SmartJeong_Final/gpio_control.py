"""Member 3 indicator adapter. Pin numbering is BCM, not physical header numbering."""
import logging

PATTERNS = {'idle': 'off', 'prompt': 'on', 'listening': 'on',
            'processing': 'blink', 'output': 'on', 'error': 'error'}


class StatusLED:
    def __init__(self, config):
        self.led = None
        self.required = config.get('required', False)
        if config.get('enabled', True):
            try:
                from gpiozero import LED
                self.led = LED(int(config.get('status_led_pin', 17)))
            except Exception as error:
                logging.warning('GPIO_INIT_FAILURE=%s', type(error).__name__)
                if config.get('required', False): raise RuntimeError('Required GPIO unavailable') from error
                print('[MOCK GPIO] Hardware unavailable.')

    def set_state(self, state):
        if state not in PATTERNS: raise ValueError('Unknown LED state')
        if self.led is None:
            print('[LED]', state)
            return
        try:
            self.led.off()  # cancels any earlier background blink
            if state in ('prompt', 'listening', 'output'): self.led.on()
            elif state == 'processing': self.led.blink(on_time=.18, off_time=.18, background=True)
            elif state == 'error': self.led.blink(on_time=.10, off_time=.10, n=5, background=True)
        except Exception as error:
            logging.warning('GPIO_RUNTIME_FAILURE=%s', type(error).__name__)
            self.close()
            if self.required:
                raise RuntimeError('Required GPIO write failed') from error
            print('[GPIO FAILURE] Indicator unavailable; continuing in degraded mode.')

    def close(self):
        if self.led:
            try: self.led.close()
            except Exception: pass
            self.led = None
