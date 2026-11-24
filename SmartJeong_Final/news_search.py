"""Public Google News RSS aggregation, not a full-article or AI service."""
import logging
import re
from urllib.parse import urlencode,urlparse
from xml.etree import ElementTree
from services import clean_text,result

US_TRENDS_RSS = 'https://trends.google.com/trending/rss?geo=US'


def _search_volume(item):
    value = item.findtext('{*}approx_traffic', '').replace(',', '').strip()
    match = re.fullmatch(r'(\d+(?:\.\d+)?)([KMkm]?)\+?', value)
    if not match:
        return 0
    amount, suffix = match.groups()
    return float(amount) * {'': 1, 'k': 1000, 'm': 1000000}[suffix.lower()]


def _us_trends(service):
    feed = ElementTree.fromstring(service.fetch(US_TRENDS_RSS))
    items = sorted(feed.findall('./channel/item'), key=_search_volume, reverse=True)
    stories = []
    topics = set()
    for item in items:
        topic = clean_text(item.findtext('title', ''), 120)
        if not topic or topic.casefold() in topics:
            continue
        for article in item.findall('{*}news_item'):
            headline = clean_text(article.findtext('{*}news_item_title', ''), 240)
            publisher = clean_text(article.findtext('{*}news_item_source', ''), 100)
            link = article.findtext('{*}news_item_url', '').strip()
            if headline and publisher and urlparse(link).scheme == 'https' and urlparse(link).hostname:
                stories.append({
                    'title': f'{topic}: {headline}',
                    'summary': 'Open the source link for the full article.',
                    'publisher': publisher,
                    'link': link,
                    'published': '',
                })
                topics.add(topic.casefold())
                break
        if len(stories) == 3:
            break
    if not stories:
        raise ValueError('No U.S. trending stories available')
    return result('news', {
        'headlines': [story['title'] for story in stories],
        'stories': stories,
        'query': '',
        'coverage': 'U.S. search trends ranked by available search volume.',
    }, 'Google Trends Trending Now (U.S.)', False)


def fetch_news(service,query=''):
    import feedparser
    query=' '.join(query.split())[:120]
    if service.config.get('offline'):
        if query:raise ValueError('Keyword search needs an internet connection')
        return service.news()
    if not query:
        try:
            return _us_trends(service)
        except (OSError, ValueError, ElementTree.ParseError) as error:
            logging.info('U.S. trends unavailable, using U.S. Google News headlines: %s', type(error).__name__)
    base='https://news.google.com/rss'
    params={'hl':'en-US','gl':'US','ceid':'US:en'}
    if query:base+='/search';params['q']=query
    url=base+'?'+urlencode(params)
    try: raw=service.fetch(url)
    except OSError: raw=service.fetch(url)  # one bounded retry for a transient connection failure
    feed=feedparser.parse(raw)
    if feed.bozo:raise ValueError('Unreadable news feed')
    stories=[];publishers=set();titles=set()
    for entry in feed.entries:
        source=entry.get('source',{})
        publisher=clean_text(source.get('title',''),100)
        key=urlparse(source.get('href','')).hostname or publisher.casefold()
        title=clean_text(entry.get('title',''),240)
        if not publisher or not title or key in publishers or title.casefold() in titles:continue
        link=entry.get('link','')
        if not link.startswith('https://'):continue
        summary=clean_text(entry.get('summary',''),900)
        if summary.replace(publisher,'').strip() in (title,title.removesuffix(' - '+publisher)) or len(summary)<len(title)+20:
            summary='Open the source link for the full article; this feed supplies a headline only.'
        stories.append({'title':title,'summary':summary,'published':entry.get('published',''),'publisher':publisher,'link':link})
        publishers.add(key);titles.add(title.casefold())
        if len(stories)==3:break
    if not stories:raise ValueError('No matching publishers found; try broader keywords')
    coverage = f'{len(stories)} of 3 requested publishers found.' if query else 'U.S. top headlines (search trends unavailable).'
    return result('news',{'headlines':[s['title'] for s in stories],'stories':stories,
        'query':query,'coverage':coverage},'Google News RSS',False)
