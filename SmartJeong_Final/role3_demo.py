"""Member 3 demonstration, independent of voice models and all data services."""
import argparse
import threading
from config import load_config
from display_interface import DisplayManager, TkDashboard
from gpio_control import StatusLED


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hardware', action='store_true')
    parser.add_argument('--tk', action='store_true')
    args = parser.parse_args()
    config = load_config()
    if not args.hardware:
        config['display']['enabled'] = False
        config['gpio']['enabled'] = False
    else:
        config['display']['required'] = True
        config['gpio']['required'] = True
    stop = threading.Event()
    display = DisplayManager(config['display'], stop)
    led = StatusLED(config['gpio'])
    def sequence():
        try:
            for state, action in [
                ('idle', display.show_idle), ('prompt', display.show_menu),
                ('listening', display.show_listening),
                ('processing', lambda: display.show_processing('weather')),
                ('output', lambda: display.show_result('DEMO WEATHER', 'Tampa\n82F partly cloudy\nFeels 85F\nWind 7 mph\nLong text appears on a second page.')),
                ('error', lambda: display.show_error('Simulated service timeout. Return to idle.')),
                ('idle', display.show_idle)]:
                if stop.is_set(): break
                led.set_state(state)
                action()
                display.hold(3)
        finally:
            led.close()
            display.close()
            stop.set()
    if args.tk:
        dashboard = TkDashboard(display, stop)
        threading.Thread(target=sequence, daemon=True).start()
        dashboard.run()
    else:
        try: sequence()
        except KeyboardInterrupt: stop.set()


if __name__ == '__main__': main()
