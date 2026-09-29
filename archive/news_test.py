import feedparser

# RSS-лента РБК (финансы)
url = "https://rssexport.rbc.ru/rbcnews/news/30/full.rss"

feed = feedparser.parse(url)

print(f"Источник: {feed.feed.title}")
print(f"Найдено новостей: {len(feed.entries)}")
print()

for i, entry in enumerate(feed.entries[:5], 1):
    print(f"{i}. {entry.title}")
    print(f"   Ссылка: {entry.link}")
    print(f"   Дата: {entry.published}")
    print()