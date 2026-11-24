"""Member 2 boundary: fetch/validate data; presentation is handled elsewhere."""
import json
import logging
import math
import re
import time
from datetime import date, datetime, time as clock_time, timedelta
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent


def clean_text(value, limit=180):
    return ' '.join(unescape(re.sub(r'<[^>]*>', '', str(value))).split())[:limit]


def result(kind, data, source, demo=False):
    return {'ok': True, 'kind': kind, 'data': data, 'source': source, 'demo': demo}


def error_briefing(title, message):
    return {'ok': False, 'title': title, 'speech': message, 'display': message}


class InformationServices:
    def __init__(self, config, now=None, fetch=None):
        self.config = config
        self.zone = ZoneInfo(config.get('timezone', 'America/New_York'))
        self.now = now or (lambda: datetime.now(self.zone))
        self.fetch = fetch or self._fetch

    def _fetch(self, url, params=None):
        """HTTPS, finite connect/read timeouts, size cap, overall transfer budget."""
        import requests
        if not url.startswith('https://'):
            raise ValueError('Only HTTPS feeds are supported')
        deadline = time.monotonic() + 12
        with requests.get(url, params=params, timeout=(3, 4), stream=True) as response:
            response.raise_for_status()
            if not response.url.startswith('https://'):
                raise ValueError('Insecure redirect')
            pieces, size = [], 0
            for piece in response.iter_content(8192):
                size += len(piece)
                if size > 2_000_000 or time.monotonic() > deadline:
                    raise ValueError('Feed exceeds transfer budget')
                pieces.append(piece)
            return b''.join(pieces)

    def schedule(self):
        from icalendar import Calendar
        import recurring_ical_events
        settings = self.config['schedule']
        url = settings.get('ics_url', '').strip()
        if url and self.config.get('offline', False):
            raise ValueError('Private feed unavailable in offline mode')
        raw = self.fetch(url) if url else (BASE_DIR / settings['local_file']).read_bytes()
        calendar = Calendar.from_ical(raw)
        for event in calendar.walk('VEVENT'):
            if 'DTSTART' not in event or 'UID' not in event:
                raise ValueError('Calendar event is missing DTSTART or UID')
        start = datetime.combine(self.now().astimezone(self.zone).date(), clock_time(), self.zone)
        end = start + timedelta(days=1)
        events = []
        for event in recurring_ical_events.of(calendar).between(start, end):
            if str(event.get('STATUS', '')).upper() == 'CANCELLED':
                continue
            value = event.decoded('DTSTART')
            if isinstance(value, datetime):
                local = value.astimezone(self.zone) if value.tzinfo else value.replace(tzinfo=self.zone)
                label = local.strftime('%I:%M %p').lstrip('0') if local >= start else 'Ongoing'
                order = local
            elif isinstance(value, date):
                label, order = 'All day', start
            else:
                raise ValueError('Invalid start date')
            events.append({'time': label, 'summary': clean_text(event.get('SUMMARY', 'Event')), 'order': order})
        events.sort(key=lambda item: (item['order'], item['summary']))
        total = len(events)
        selected = [{'time': x['time'], 'summary': x['summary']} for x in events[:3]]
        return result('schedule', {'events': selected, 'total': total},
                      'private calendar' if url else 'local calendar', settings.get('demo', True) and not url)

    def pills(self):
        settings = self.config['pills']
        raw = json.loads((BASE_DIR / settings['file']).read_text())
        if not isinstance(raw, list):
            raise ValueError('Pills must be a list')
        now = self.now().astimezone(self.zone)
        items = []
        for entry in raw:
            if not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not entry['name'].strip():
                raise ValueError('Invalid reminder name')
            if not isinstance(entry.get('times'), list) or not entry['times']:
                raise ValueError('Invalid reminder times')
            for value in entry['times']:
                if not isinstance(value, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
                    raise ValueError('Expected HH:MM')
                hour, minute = map(int, value.split(':'))
                scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                # Earlier reminders are not inferred to be missed or taken.
                # Keep the current minute visible; otherwise find the next occurrence.
                if scheduled < now.replace(second=0, microsecond=0):
                    scheduled += timedelta(days=1)
                items.append({'name': clean_text(entry['name'], 60), 'scheduled': scheduled})
        items.sort(key=lambda item: (item['scheduled'], item['name']))
        selected = []
        for item in items[:3]:
            at = item['scheduled']
            selected.append({'name': item['name'], 'time': at.strftime('%I:%M %p').lstrip('0'),
                             'day': 'Tomorrow' if at.date() > now.date() else 'Today'})
        return result('pills', {'items': selected, 'total': len(items)}, 'local reminder schedule', settings.get('demo', True))

    def weather(self):
        settings = self.config['weather']
        demo = self.config.get('offline', False)
        if demo:
            payload = json.loads((BASE_DIR / 'data/weather.json').read_text())
        else:
            payload = json.loads(self.fetch('https://api.open-meteo.com/v1/forecast', {
                'latitude': settings['latitude'], 'longitude': settings['longitude'],
                'current': 'temperature_2m,apparent_temperature,weather_code,wind_speed_10m',
                'temperature_unit': 'fahrenheit', 'wind_speed_unit': 'mph', 'timezone': 'auto'}))
        current = payload['current']
        values = [float(current[k]) for k in ('temperature_2m', 'apparent_temperature', 'wind_speed_10m')]
        if not all(math.isfinite(x) for x in values):
            raise ValueError('Invalid weather numbers')
        temp, feels, wind = map(round, values)
        return result('weather', {'location': settings['location_name'], 'temperature': temp,
                      'feels': feels, 'wind': wind, 'condition': self._weather_code(int(current['weather_code'])),
                      'timezone': payload.get('timezone'), 'observed': clean_text(current['time'], 30)}, 'Open-Meteo' if not demo else 'synthetic weather', demo)

    def news(self):
        import feedparser
        demo = self.config.get('offline', False)
        raw = (BASE_DIR / 'data/news.xml').read_bytes() if demo else self.fetch(self.config['news']['rss_url'])
        feed = feedparser.parse(raw)
        if feed.bozo:
            raise ValueError('Malformed RSS')
        headlines, stories = [], []
        count = max(1, min(3, int(self.config['news'].get('headline_count', 3))))
        for entry in feed.entries:
            title = clean_text(entry.get('title', ''))
            if title and title not in headlines:
                headlines.append(title)
                stories.append({'title': title, 'summary': clean_text(entry.get('summary', ''), 900),
                                'published': clean_text(entry.get('published', ''), 100)})
            if len(headlines) == count:
                break
        if not headlines:
            raise ValueError('Empty RSS')
        return result('news', {'headlines': headlines, 'stories': stories}, 'synthetic RSS' if demo else clean_text(feed.feed.get('title', 'RSS')), demo)

    def dispatch(self, command):
        actions = {'schedule': self.schedule, 'pills': self.pills, 'weather': self.weather, 'news': self.news}
        if command not in actions:
            return error_briefing('Try again', 'I did not understand. Please try again.')
        try:
            return actions[command]()
        except Exception as error:
            # Do not expose private feed URLs, names, or medication data in logs.
            logging.warning('SERVICE=%s FAILURE=%s', command, type(error).__name__)
            return error_briefing(command.title(), f'{command.title()} is unavailable right now. Please try again later.')

    @staticmethod
    def _weather_code(code):
        if code == 0: return 'clear'
        if code in (1, 2, 3): return 'partly cloudy'
        if code in (45, 48): return 'foggy'
        if code in (51, 53, 55, 56, 57): return 'drizzling'
        if code in (61, 63, 65, 66, 67, 80, 81, 82): return 'rainy'
        if code in (71, 73, 75, 77, 85, 86): return 'snowy'
        if code in (95, 96, 99): return 'stormy'
        return 'conditions unavailable'
