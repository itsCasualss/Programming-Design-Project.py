import unittest
from contextlib import contextmanager
from PIL import Image, ImageDraw, ImageFont
from display_interface import DisplayManager

class TFTTests(unittest.TestCase):
    def test_color_render_and_pagination(self):
        manager = DisplayManager({'enabled': False, 'backend': 'st7735'})
        class Device:
            width, height = 128, 160
        manager.device = Device()
        manager.font = ImageFont.load_default_imagefont()
        frames = []
        @contextmanager
        def canvas(device):
            frame = Image.new('RGB', (device.width, device.height))
            yield ImageDraw.Draw(frame)
            frames.append(frame)
        manager.canvas = canvas
        manager.show_result('NEWS', '\n'.join('Line '+str(i) for i in range(22)))
        self.assertEqual(len(manager.pages), 3)
        self.assertTrue(all(len(p) <= 9 for p in manager.pages))
        self.assertEqual(frames[-1].getpixel((0, 0)), (179, 154, 119))
        manager.show_error('Network unavailable')
        self.assertEqual(frames[-1].getpixel((0, 0)), (201, 134, 118))

if __name__ == '__main__':
    unittest.main()
