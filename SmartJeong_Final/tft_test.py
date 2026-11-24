"""Standalone physical TFT test; no voice, network, or status LED needed."""
import time
from config import load_config
from display_interface import DisplayManager

def main():
    config = load_config()['display']
    config.update(enabled=True, required=True, backend='st7735')
    display = DisplayManager(config)
    try:
        for color in ['red', 'green', 'blue', 'white']:
            print('Confirm screen color:', color)
            with display.canvas(display.device) as draw:
                draw.rectangle(display.device.bounding_box, fill=color)
            time.sleep(2)
        with display.canvas(display.device) as draw:
            draw.rectangle(display.device.bounding_box, outline='white')
            draw.text((5, 25), 'TFT TEST 128x160', font=display.font, fill='cyan')
        input('Check text and all four border edges. Enter to finish: ')
    finally:
        display.close()

if __name__ == '__main__':
    main()
