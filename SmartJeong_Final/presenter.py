from datetime import datetime
from friendly_dates import date_label, time_label
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from speech_output import Speaker

def readable_time(value, zone=None, rss=False):
    try:
        stamp = parsedate_to_datetime(value) if rss else datetime.fromisoformat(value)
        if zone:
            stamp = stamp.astimezone(ZoneInfo(zone)) if stamp.tzinfo else stamp.replace(tzinfo=ZoneInfo(zone))
        label = date_label(stamp) + ' at ' + time_label(stamp)
        return label + (' ' + stamp.tzname() if stamp.tzinfo else ' (source local time)')
    except (ValueError, TypeError, KeyError):
        return value or 'Publication time unavailable'

"""Member 3: one presentation contract for full speech and condensed OLED text."""

def format_briefing(briefing):
    if not briefing['ok']:
        return briefing
    kind, data = briefing['kind'], briefing['data']
    demo = briefing.get('demo', False)
    title = ('DEMO ' if demo else '') + kind.title()
    prefix = 'Demonstration data. ' if demo else ''
    if kind == 'schedule':
        rows = [f"{x['time']}: {x['summary']}" for x in data['events']]
        message = '; '.join(rows) if rows else 'No events today.'
        if data['total'] > len(rows):
            message += f". Showing {len(rows)} of {data['total']} events."
        speech, display = message, message
    elif kind == 'pills':
        rows = [f"{x['day']} {x['time']}: {x['name']}" for x in data['items']]
        speech = 'Next scheduled reminders. ' + '; '.join(rows) if rows else 'No reminders configured.'
        speech += ('. These are fictional labels.' if demo else '.') + ' This device does not know whether an item was taken.'
        display = '\n'.join(rows) + '\nTaken status: unknown'
    elif kind == 'weather':
        speech = (f"In {data['location']}, {data['temperature']} degrees Fahrenheit, {data['condition']}. "
                  f"Feels like {data['feels']}. Wind {data['wind']} miles per hour. "
                  f"Updated {readable_time(data['observed'], data.get('timezone'))}.")
        display = (f"{data['location']}\n\n{data['temperature']}°F · {data['condition'].title()}\n"
                   f"Feels like {data['feels']}°F · Wind {data['wind']} mph\n\n"
                   f"Updated {readable_time(data['observed'], data.get('timezone'))}\nSource: {briefing['source']}")
    elif kind == 'news':
        speech = 'Headlines. ' + '. '.join(data['headlines']) + '.'
        stories = data.get('stories', [])
        if stories:
            display = '\n\n'.join(f"{i+1}. {x['title']}\n{x.get('publisher', briefing['source'])} · {readable_time(x['published'], 'America/New_York', rss=True)}\n{x['summary'] or 'No description supplied by the feed.'}" for i, x in enumerate(stories))
            display = f"Source: {briefing['source']} · {data.get('coverage', '')}\n\n" + display
            links = [x.get('link','') for x in stories]
            if any(links): display += '\n\nREAD ORIGINAL ARTICLES\n' + '\n'.join(f'{i+1}. {link}' for i,link in enumerate(links) if link)
            speech = 'News briefing. ' + ' '.join(x['title'] + '. ' + x['summary'] for x in stories)
        else:
            display = '\n'.join(f'{i+1}. {x}' for i, x in enumerate(data['headlines']))
    else:
        raise ValueError('Unknown briefing type')
    return {'ok': True, 'title': title, 'speech': prefix + speech, 'display': display}


class Presenter:
    def __init__(self, display, speaker, status_led=None, hold_seconds=3):
        self.display, self.speaker = display, speaker
        self.hold_seconds = hold_seconds

    def present(self, briefing, dismissed=None):
        rendered = format_briefing(briefing)
        self.display.show_result(rendered['title'], rendered['display'])
        if dismissed is not None and isinstance(self.speaker, Speaker):
            spoken = self.speaker.speak(rendered['speech'], dismissed)
        else:
            spoken = self.speaker.speak(rendered['speech'])
        if spoken is False:
            self.display.show_error('Audio failed. Check output device. Briefing was displayed.')
        if self.hold_seconds > 0: self.display.hold(self.hold_seconds)
        return spoken
