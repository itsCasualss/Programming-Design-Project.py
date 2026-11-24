"""Interactive ST7735 bring-up. Only saves a profile you visually confirm."""
import argparse
import json
from pathlib import Path
from config import BASE_DIR, load_config
from display_interface import DisplayManager
from setup_personal import private_write

PROFILES = [
    ('standard', {'h_offset':0, 'v_offset':0, 'bgr':False,'inverse':False}),
    ('offset panel', {'h_offset':0, 'v_offset':24, 'bgr':False,'inverse':False}),
    ('green tab offset', {'h_offset':1, 'v_offset':2, 'bgr':True,'inverse':False}),
    ('RGB swapped', {'h_offset':0, 'v_offset':0, 'bgr':True,'inverse':False}),
    ('inverted', {'h_offset':0, 'v_offset':0, 'bgr':False,'inverse':True}),
]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--rotation',type=int,choices=range(4),default=1)
    args=parser.parse_args()
    config=load_config()['display'].copy()
    device=Path('/dev/spidev%d.%d' % (config.get('spi_port',0),config.get('spi_device',0)))
    if not device.exists():
        raise SystemExit(f'{device} is missing. Enable SPI in sudo raspi-config, then reboot.')
    print('Close main.py first. Wiring: CE0 GPIO8, DC GPIO24, RST GPIO25, MOSI GPIO10, SCLK GPIO11.')
    print('A white backlight alone does not confirm SPI communication. Stop if wiring differs.')
    for name,profile in PROFILES:
        settings={**config,**profile,'enabled':True,'required':True,'backend':'st7735','rotate':args.rotation,'spi_speed_hz':500000}
        print('Testing',name,profile)
        display=DisplayManager(settings)
        try:
            w,h=display.device.size
            with display.canvas(display.device) as draw:
                for index,color in enumerate(('red','green','blue')):
                    draw.rectangle((index*w//3,0,(index+1)*w//3-1,h-1),fill=color)
                draw.rectangle((0,0,w-1,h-1),outline='white')
                draw.rectangle((2,h//2-12,w-3,h//2+12),fill='black')
                draw.text((5,h//2-6),'JARVIS R G B',font=display.font,fill='white')
            answer=input('Correct red/green/blue, text and full border? y saves / Enter next / q quits: ').strip().lower()
            if answer=='q':return
            if answer=='y':
                path=BASE_DIR/'config.local.json'
                local=json.loads(path.read_text()) if path.exists() else {}
                local.setdefault('display',{}).update(profile,rotate=args.rotation,spi_speed_hz=500000,backend='st7735')
                private_write(path,json.dumps(local,indent=2)+'\n')
                print('Confirmed profile saved. Run main.py --dual --no-audio.');return
        finally:display.close()
    print('No confirmed profile. Power down and verify wiring/controller/model. Do not change supply voltage based on this test.')

if __name__=='__main__':main()
