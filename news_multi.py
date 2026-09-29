import feedparser

SOURCES = {
    "РБК": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
    "Интерфакс": "https://www.interfax.ru/rss.asp",
    "Коммерсантъ": "https://www.kommersant.ru/RSS/news.xml",
}

for name, url in SOURCES.items():
    try:
        feed = feedparser.parse(url)
        print(f"\n{name}: {len(feed.entries)} новостей")
        for entry in feed.entries[:3]:
            print(f"  • {entry.title}")
    except Exception as e:
        print(f"\n{name}: ошибка — {e}")