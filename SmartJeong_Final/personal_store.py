"""Validated dashboard data entry; local settings remain private."""
import json
from datetime import datetime
from uuid import uuid4
from icalendar import Calendar,Event
from config import BASE_DIR
from setup_personal import private_write
from friendly_dates import parse_date,parse_time,date_label,time_label

def preview_entry(kind,name,day,times,zone):
    name=name.strip()
    if not name:raise ValueError('Please enter a name.')
    if len(name)>120:raise ValueError('Keep the name under 120 characters.')
    if kind=='calendar':
        start=datetime.combine(parse_date(day,datetime.now(zone).date()),parse_time(times),zone)
        return {'name':name,'start':start},f'{name}\n{date_label(start)} at {time_label(start)}\nTimezone: {zone}'
    values=sorted(set(parse_time(t) for t in times.split(',')))
    return {'name':name,'times':[t.strftime('%H:%M') for t in values]},name+'\nEvery day at '+', '.join(time_label(t) for t in values)

def save_entry(kind,entry):
    local_path=BASE_DIR/'config.local.json'
    local=json.loads(local_path.read_text()) if local_path.exists() else {}
    if kind=='calendar':
        if local.get('schedule',{}).get('ics_url'):
            raise ValueError('A private feed is connected. Edit that calendar at its provider; local entry will not replace it.')
        path=BASE_DIR/'data/personal_calendar.ics'
        calendar=Calendar.from_ical(path.read_bytes()) if path.exists() else Calendar()
        if not path.exists():calendar.add('version','2.0');calendar.add('prodid','-//Jarvis//Calendar//EN')
        event=Event();event.add('uid',str(uuid4()));event.add('summary',entry['name']);event.add('dtstart',entry['start'])
        event.add('dtstamp',datetime.now(entry['start'].tzinfo));calendar.add_component(event)
        private_write(path,calendar.to_ical().decode())
        local.setdefault('schedule',{}).update(ics_url='',local_file='data/personal_calendar.ics',demo=False)
    else:
        path=BASE_DIR/'data/personal_pills.json';items=json.loads(path.read_text()) if path.exists() else []
        items.append(entry);private_write(path,json.dumps(items,indent=2)+'\n')
        local.setdefault('pills',{}).update(file='data/personal_pills.json',demo=False)
    private_write(local_path,json.dumps(local,indent=2)+'\n')
