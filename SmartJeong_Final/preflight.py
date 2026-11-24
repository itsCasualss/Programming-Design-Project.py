"""Aggregate dependency/config/device-access checks; never claim panel detection."""
import argparse
import importlib
import os
from pathlib import Path
import platform
import sys

MODULES = ('requests', 'feedparser', 'icalendar', 'recurring_ical_events',
           'PIL.Image', 'PIL.ImageFont', 'luma.core.interface.serial',
           'luma.core.render', 'luma.lcd.device', 'spidev', 'RPi.GPIO',
           'gpiozero', 'gpiozero.pins.rpigpio')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hardware', action='store_true')
    args = parser.parse_args()
    failures = []
    def check(label, operation):
        try:
            operation()
            print('PASS:', label)
        except Exception as error:
            failures.append(label)
            print(f'FAIL: {label}: {type(error).__name__}: {error}')
    print(f'Python {sys.version.split()[0]} / {platform.machine()} / {sys.executable}')
    for name in MODULES:
        check(name, lambda name=name: importlib.import_module(name))
    def configuration():
        from config import load_config
        from zoneinfo import ZoneInfo
        cfg = load_config()
        if cfg['display'].get('backend') != 'st7735':
            raise ValueError('This bring-up profile requires display.backend=st7735')
        if not cfg['display'].get('enabled') or not cfg['gpio'].get('enabled'):
            raise ValueError('Display and GPIO must be enabled for hardware verification')
        if int(cfg['gpio']['status_led_pin']) != 17:
            raise ValueError('Wiring profile requires status LED BCM17 (physical 11)')
        if int(cfg['display'].get('rotate', 1)) not in range(4):
            raise ValueError('rotate must be 0..3')
        ZoneInfo(cfg['display'].get('timezone', cfg['timezone']))
    check('configuration', configuration)
    if args.hardware:
        def access(path):
            if not Path(path).exists():
                raise RuntimeError(f'{path} absent; enable SPI and reboot if applicable')
            if not os.access(path, os.R_OK | os.W_OK):
                raise PermissionError(f'{path}: check spi/gpio group membership, then reconnect')
        check('SPI permissions', lambda: access('/dev/spidev0.0'))
        check('GPIO permissions', lambda: access('/dev/gpiomem'))
        def spi_open():
            import spidev
            bus = spidev.SpiDev()
            try:
                bus.open(0, 0)
            finally:
                bus.close()
        check('SPI open/close', spi_open)
    print(f'\n{len(failures)} failed checks. Physical screen/LED/audio observations still required.')
    return int(bool(failures))

if __name__ == '__main__':
    raise SystemExit(main())
