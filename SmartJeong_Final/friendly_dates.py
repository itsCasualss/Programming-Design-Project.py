"""Human-facing dates; reject ambiguous numeric dates rather than guessing."""
import re
from datetime import datetime, timedelta

def date_label(value):
    day=value.day
    suffix='th' if 10 < day % 100 < 14 else {1:'st',2:'nd',3:'rd'}.get(day%10,'th')
    return f'{value:%B} {day}{suffix}, {value.year}'

def time_label(value):return value.strftime('%I:%M %p').lstrip('0')

def parse_date(text, today=None):
    today=today or datetime.now().date(); raw=text.strip().lower()
    if raw in ('today','tomorrow'):return today+timedelta(days=raw=='tomorrow')
    raw=re.sub(r'(\d)(st|nd|rd|th)\b',r'\1',raw).replace(',','')
    if re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}',raw):
        a,b,y=map(int,raw.split('/'))
        if a<=12 and b<=12 and a!=b:raise ValueError('That date is ambiguous. Use a month name, such as November 11th, 2026.')
        return datetime.strptime(raw,'%d/%m/%Y' if a>12 else '%m/%d/%Y').date()
    for fmt in ('%Y-%m-%d','%B %d %Y','%b %d %Y','%d %B %Y','%d %b %Y','%B %d','%b %d'):
        try:
            value=datetime.strptime(raw,fmt)
            return value.replace(year=today.year).date() if '%Y' not in fmt else value.date()
        except ValueError:pass
    raise ValueError('Use November 11th, 2026, 2026-11-11, today, or tomorrow.')

def parse_time(text):
    raw=re.sub(r'\s+','',text.strip().lower()).replace('.','')
    for fmt in ('%I:%M%p','%I%p','%H:%M','%H%M'):
        try:
            if fmt=='%H%M' and not re.fullmatch(r'\d{4}',raw):continue
            return datetime.strptime(raw,fmt).time()
        except ValueError:pass
    raise ValueError('Use a time such as 11:20 PM, 8am, 23:20, or 2320.')
