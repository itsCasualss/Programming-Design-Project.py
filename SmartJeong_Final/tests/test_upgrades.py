import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from datetime import date
from zoneinfo import ZoneInfo
from tempfile import TemporaryDirectory
from unittest.mock import patch
from friendly_dates import parse_date,parse_time,date_label,time_label
from personal_store import preview_entry,save_entry
from news_search import fetch_news
from config import load_config
from services import InformationServices

class UpgradeTests(unittest.TestCase):
    def test_active_service_lifecycle(self):
        from dashboard import selected_service
        for service in ('schedule','pills','weather','news'):
            active=selected_service(None,'PROCESSING',service.title(),'processing')
            self.assertEqual(active,service)
            self.assertEqual(selected_service(active,'DEMO '+service.title(),'Result','output'),service)
            self.assertEqual(selected_service(active,'ERROR','Unavailable','error'),service)
            self.assertIsNone(selected_service(active,'BRIEFING BOX','','idle'))

    def test_dates_and_ambiguity(self):
        for raw in ('November 11th, 2026','nov 11 2026','2026-11-11'):
            self.assertEqual(date_label(parse_date(raw)),'November 11th, 2026')
        self.assertEqual(parse_date('tomorrow',date(2026,12,31)),date(2027,1,1))
        with self.assertRaises(ValueError):parse_date('03/04/2026')
        with self.assertRaises(ValueError):parse_date('February 30th, 2026')
        self.assertEqual(date_label(date(2026,11,21)),'November 21st, 2026')
    def test_times(self):
        for value in ('11:20 PM','11:20pm','23:20','2320'):
            self.assertEqual(time_label(parse_time(value)),'11:20 PM')
        self.assertEqual(time_label(parse_time('8am')),'8:00 AM')
        with self.assertRaises(ValueError):parse_time('25:00')
    def test_persistence(self):
        with TemporaryDirectory() as folder,patch('personal_store.BASE_DIR',Path(folder)):
            entry,preview=preview_entry('calendar','Project test','November 11th, 2026','2320',ZoneInfo('America/New_York'))
            self.assertIn('11:20 PM',preview);save_entry('calendar',entry)
            self.assertIn('Project test',(Path(folder)/'data/personal_calendar.ics').read_text())
            item,_=preview_entry('reminders','Test','','8am,20:30',ZoneInfo('America/New_York'))
            save_entry('reminders',item)
            self.assertIn('20:30',(Path(folder)/'data/personal_pills.json').read_text())
    def test_news_distinct_publishers_and_fewer(self):
        raw='<rss version="2.0"><channel><title>News</title>'
        for index,publisher in enumerate(('A','A','B','C')):
            raw+=f'<item><title>Story {index}</title><link>https://example.com/{index}</link><source url="https://{publisher.lower()}.example.com">{publisher}</source><description>A headline.</description></item>'
        raw+='</channel></rss>'
        urls=[]
        def fetch(url):urls.append(url);return raw.encode()
        config=load_config();config['offline']=False
        result=fetch_news(InformationServices(config,fetch=fetch),'space & science')
        self.assertEqual([s['publisher'] for s in result['data']['stories']],['A','B','C'])
        self.assertIn('q=space+%26+science',urls[0])
        raw=raw.replace('<source url="https://b.example.com">B</source>','<source url="https://a.example.com">A</source>')
        self.assertEqual(len(fetch_news(InformationServices(config,fetch=fetch))['data']['stories']),2)
if __name__=='__main__':unittest.main()
