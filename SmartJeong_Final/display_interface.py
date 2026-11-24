"""OLED worker-side rendering; optional Tk window consumes messages on main thread."""
import logging
import queue
import textwrap
import time
from datetime import datetime
from zoneinfo import ZoneInfo


def wrap_pages(text, width=20, lines_per_page=4):
    # Conservative fixed font geometry: 20 * 6 pixels = 120 < 128.
    lines = []
    safe = str(text).encode('ascii', 'replace').decode('ascii')
    for paragraph in safe.splitlines():
        lines.extend(textwrap.wrap(paragraph, width) or [''])
    lines = lines or ['']
    return [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]


class DisplayManager:
    def __init__(self, config, stop=None):
        self.device = None
        self.config = config
        self.tft = config.get('backend', 'ssd1306') == 'st7735'
        self.stop = stop
        self.zone = ZoneInfo(config.get('timezone', 'America/New_York'))
        self.messages = queue.Queue(maxsize=20)
        self.title, self.body, self.state = '', '', 'startup'
        self.pages, self.page, self.changed = [[]], 0, time.monotonic()
        self.last_clock = ''
        self.page_seconds = float(config.get('page_seconds', 3))
        if config.get('enabled', True):
            try:
                from luma.core.render import canvas
                from PIL import ImageFont
                if self.tft:
                    from luma.core.interface.serial import spi
                    from luma.lcd.device import st7735
                    serial = spi(port=int(config.get('spi_port', 0)), device=int(config.get('spi_device', 0)), gpio_DC=int(config.get('dc_pin', 24)), gpio_RST=int(config.get('reset_pin', 25)), bus_speed_hz=int(config.get('spi_speed_hz', 1000000)))
                    self.device = st7735(serial, width=160, height=128,
                        rotate=int(config.get('rotate', 1)),
                        h_offset=int(config.get('h_offset', 0)),
                        v_offset=int(config.get('v_offset', 0)),
                        bgr=bool(config.get('bgr', False)), inverse=bool(config.get('inverse', False)), backlight=lambda enabled: None)
                else:
                    from luma.core.interface.serial import i2c
                    from luma.oled.device import ssd1306
                    serial = i2c(port=config.get('i2c_port', 1), address=int(str(config.get('i2c_address', '0x3C')), 0))
                    self.device = ssd1306(serial, width=128, height=64)
                self.canvas, self.font = canvas, ImageFont.load_default()
                # Use bundled Pillow legacy bitmap font for predictable 6x11 geometry.
                if hasattr(ImageFont, 'load_default_imagefont'):
                    self.font = ImageFont.load_default_imagefont()
            except Exception as error:
                self.device = None
                logging.warning('DISPLAY_INIT_FAILURE=%s: %s', type(error).__name__, error)
                if config.get('required', False):
                    raise RuntimeError('Required display is unavailable') from error
                print('[MOCK DISPLAY] Hardware unavailable; console active.')

    def _publish(self):
        item = (self.title, self.body, self.state)
        try:
            self.messages.put_nowait(item)
        except queue.Full:
            try: self.messages.get_nowait()
            except queue.Empty: pass  # Tk may have drained it since put()
            self.messages.put_nowait(item)

    def _draw(self):
        if self.device is None:
            return
        try:
            with self.canvas(self.device) as draw:
                if self.tft:
                    color = '#b39a77' if self.state != 'error' else '#c98676'
                    draw.rectangle((0, 0, self.device.width-1, 17), fill=color)
                    draw.text((4, 3), self.title[:20], font=self.font, fill='black')
                    for i, line in enumerate(self.pages[self.page]):
                        draw.text((4, 24+i*12), line, font=self.font, fill='#777970' if self.state == 'idle' else '#f2efe8')
                    draw.text((4, self.device.height-13), f'{self.state.upper()} {self.page+1}/{len(self.pages)}', font=self.font, fill=color)
                    return
                title = self.title.encode('ascii', 'replace').decode('ascii')[:20]
                draw.text((0, 0), title, font=self.font, fill='white')
                for i, line in enumerate(self.pages[self.page]):
                    draw.text((0, 13 + i * 10), line, font=self.font, fill='white')
                draw.text((0, 53), f'{self.page+1}/{len(self.pages)}', font=self.font, fill='white')
        except Exception as error:
            logging.warning('DISPLAY_RUNTIME_FAILURE=%s: %s', type(error).__name__, error)
            if self.config.get('required', False):
                raise RuntimeError('Required display write failed') from error
            self.device = None
            self.body = 'Display write failed. Check wiring.\n' + self.body
            self._publish()
            print('[DISPLAY FAILURE] Continuing with console/Tk; hardware demo is degraded.')

    def _render(self, title, body='', state=None):
        self.title, self.body = str(title), str(body)
        if state: self.state = state
        height = getattr(self.device, 'height', 160)
        self.pages, self.page = wrap_pages(body, width=max(16, (getattr(self.device, 'width', 128)-8)//6), lines_per_page=max(1, (height-42)//12) if self.tft else 4), 0
        self.changed = time.monotonic()
        print(f'[DISPLAY {self.state}] {title}\n{body}')
        self._publish()
        self._draw()

    def tick(self):
        if self.state == 'idle':
            clock = datetime.now(self.zone).strftime('%I:%M %p')
            if clock != self.last_clock:
                self.last_clock = clock
                self.show_idle()
        elif len(self.pages) > 1 and time.monotonic() - self.changed >= self.page_seconds:
            self.page = (self.page + 1) % len(self.pages)
            self.changed = time.monotonic()
            self._draw()

    def hold(self, seconds):
        # Every page receives a readable interval even when speech is disabled.
        deadline = time.monotonic() + max(seconds, len(self.pages) * self.page_seconds if self.device else seconds)
        while time.monotonic() < deadline and not (self.stop and self.stop.is_set()):
            self.tick()
            time.sleep(.05)

    def show_startup(self): self._render('BRIEFING BOX', 'Starting...', 'startup')
    def show_idle(self):
        self._render('BRIEFING BOX', datetime.now(self.zone).strftime('%I:%M %p') + '\nSay Hey Jarvis\nSchedule / Pills\nWeather / News', 'idle')
    def show_menu(self): self._render('Pwincess Jeong, how can I help?', '1 Schedule\n2 Pills\n3 Weather\n4 News', 'prompt')
    def show_listening(self): self._render('LISTENING', 'Schedule / Pills\nWeather / News', 'listening')
    def show_processing(self, command): self._render('PROCESSING', command.title(), 'processing')
    def show_result(self, title, text): self._render(title, text, 'output')
    def show_error(self, message): self._render('ERROR', message, 'error')
    def close(self):
        if self.device:
            try: self.device.clear()
            except Exception: pass


from dashboard import TkDashboard
