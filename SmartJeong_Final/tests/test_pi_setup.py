"""Real luma initialization/serialization with ONLY electrical I/O mocked."""
import builtins
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from display_interface import DisplayManager
from gpio_control import StatusLED

class PiSetupTests(unittest.TestCase):
    def test_real_st7735_driver_initialization_and_render_without_oled(self):
        from luma.core.interface.serial import spi, bitbang
        from luma.lcd.device import st7735
        gpio = Mock(LOW=0, HIGH=1, OUT=1)
        bus = Mock()
        original_import = builtins.__import__
        def no_oled(name, *args, **kwargs):
            if name.startswith('luma.oled'):
                raise ModuleNotFoundError('OLED intentionally absent')
            return original_import(name, *args, **kwargs)
        with patch.object(bitbang, '__rpi_gpio__', return_value=gpio), \
             patch.object(st7735, '__rpi_gpio__', return_value=gpio), \
             patch.object(spi, '__spidev__', return_value=bus), \
             patch('builtins.__import__', side_effect=no_oled):
            display = DisplayManager({'backend': 'st7735', 'required': True})
            try:
                self.assertEqual(display.device.size, (128, 160))
                self.assertEqual(display.device.mode, 'RGB')
                bus.open.assert_called_once_with(0, 0)
                self.assertEqual(bus.max_speed_hz, 1000000)
                gpio.setup.assert_any_call(24, gpio.OUT)
                gpio.setup.assert_any_call(25, gpio.OUT)
                for state in ('show_startup', 'show_idle', 'show_menu', 'show_listening'):
                    getattr(display, state)()
                display.show_processing('weather')
                display.show_result('WEATHER', 'Sunny\n82F')
                display.show_error('Simulated test error')
                self.assertIsNotNone(display.device)
                self.assertTrue(bus.writebytes.called or bus.writebytes2.called)
            finally:
                display.device.cleanup()

    def test_required_display_write_fails_visibly(self):
        display = DisplayManager({'enabled': False, 'required': True})
        display.device = object()
        display.canvas = Mock(side_effect=OSError('SPI failed'))
        with self.assertRaisesRegex(RuntimeError, 'display write failed'):
            display.show_result('Test', 'Body')

    def test_required_gpio_write_fails_visibly(self):
        led = StatusLED({'enabled': False, 'required': True})
        led.led = Mock()
        led.led.off.side_effect = OSError('GPIO failed')
        with self.assertRaisesRegex(RuntimeError, 'GPIO write failed'):
            led.set_state('listening')

    def test_spi_and_gpio_are_explicit_dependencies(self):
        requirements = (Path(__file__).resolve().parents[1] / 'requirements-hardware.txt').read_text()
        for dependency in ('spidev==3.8', 'RPi.GPIO==0.7.1', 'gpiozero==2.0.1', 'luma.lcd==2.13.0'):
            self.assertIn(dependency, requirements)

if __name__ == '__main__':
    unittest.main()
