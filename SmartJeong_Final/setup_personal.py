"""Configure personal calendar and reminders without editing teammate code."""
import argparse
from datetime import datetime
from getpass import getpass
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo
from icalendar import Calendar, Event
from config import BASE_DIR, load_config


def private_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as stream: stream.write(text)
    temporary.replace(path)
    path.chmod(0o600)


def validate_times(raw):
    times = [value.strip() for value in raw.split(',')]
    if not times or any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', x) for x in times):
        raise ValueError('Use 24-hour times, e.g. 08:00,20:30')
    return sorted(set(times))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('section',choices=['calendar','reminders'])
    args=parser.parse_args()
    config=load_config(); local_path=BASE_DIR/'config.local.json'
    local=json.loads(local_path.read_text()) if local_path.exists() else {}
    if args.section=='calendar':
        mode=input('Private HTTPS ICS feed (f) or local calendar (l)? ').strip().lower()
        if mode=='f':
            url=getpass('Private ICS URL (hidden): ').strip()
            parsed=urlparse(url)
            if parsed.scheme!='https' or not parsed.hostname:raise ValueError('An HTTPS ICS URL is required')
            local.setdefault('schedule',{}).update(ics_url=url,demo=False)
        elif mode=='l':
            path=BASE_DIR/'data/personal_calendar.ics'
            cal=Calendar.from_ical(path.read_bytes()) if path.exists() else Calendar()
            if not path.exists():cal.add('version','2.0');cal.add('prodid','-//Briefing Box//Local Calendar//EN')
            title=input('Event name: ').strip()
            if not title:raise ValueError('Event name cannot be blank')
            start=datetime.strptime(input('Start YYYY-MM-DD HH:MM: '),'%Y-%m-%d %H:%M').replace(tzinfo=ZoneInfo(config['timezone']))
            event=Event();event.add('uid',str(uuid4()));event.add('summary',title);event.add('dtstart',start)
            event.add('dtstamp',datetime.now(ZoneInfo('UTC')));cal.add_component(event)
            private_write(path,cal.to_ical().decode())
            local.setdefault('schedule',{}).update(ics_url='',local_file='data/personal_calendar.ics',demo=False)
        else:raise ValueError('Choose f or l')
    else:
        path=BASE_DIR/'data/personal_pills.json'
        items=json.loads(path.read_text()) if path.exists() else []
        name=input('Reminder label (your own schedule): ').strip()
        if not name:raise ValueError('Label cannot be blank')
        times=validate_times(input('Daily times HH:MM, separated by commas: '))
        items.append({'name':name,'times':times})
        private_write(path,json.dumps(items,indent=2)+'\n')
        local.setdefault('pills',{}).update(file='data/personal_pills.json',demo=False)
    private_write(local_path,json.dumps(local,indent=2)+'\n')
    print('Saved. Restart Briefing Box to load the settings.')

if __name__=='__main__':
    try:main()
    except (ValueError,KeyboardInterrupt,EOFError) as error:
        print('Setup cancelled or invalid input:',error)
        raise SystemExit(1)
