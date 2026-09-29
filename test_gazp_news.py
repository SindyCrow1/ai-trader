import os
import feedparser
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
PROXYAPI_KEY = os.getenv("PROXYAPI_KEY")
PROXYAPI_BASE_URL = os.getenv("PROXYAPI_BASE_URL", "https://api.proxyapi.ru/v1")

SOURCES = {
    "РБК": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
    "Интерфакс": "https://www.interfax.ru/rss.asp",
    "Коммерсантъ": "https://www.kommersant.ru/RSS/news.xml",
}

KEYWORDS = ["газпром", "газ", "нефт", "энерг", "экспорт", "труб"]

all_news = []
for source_name, url in SOURCES.items():
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:50]:
            title = entry.title
            summary = getattr(entry, 'summary', '')[:200]
            all_news.append({"source": source_name, "title": title, "summary": summary})
    except Exception as e:
        print(f"{source_name}: ошибка — {e}")

filtered_news = []
for item in all_news:
    text_lower = (item["title"] + " " + item["summary"]).lower()
    if any(kw in text_lower for kw in KEYWORDS):
        filtered_news.append(f"[{item['source']}] {item['title']}\n  {item['summary']}")

print(f"Всего новостей: {len(all_news)}")
print(f"После фильтра (Газпром): {len(filtered_news)}")

tech_data = """
Акция: Газпром (GAZP)
Цена: 97.58 руб.
Изменение за день: +1.23%
RSI(14): 51.9 (нейтрально)
MA20: 96.31
MA50: 91.12
MA20 > MA50 (восходящий тренд)
Объём: 1.52x к среднему (высокий)
"""

if filtered_news:
    news_text = "\n".join(filtered_news[:20])
    prompt = f"""Ты — торговый аналитик. Проанализируй Газпром.

{tech_data}

НОВОСТИ:
{news_text}

Ответь СТРОГО в формате JSON:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование на русском"
}}
"""
    
    client = OpenAI(api_key=PROXYAPI_KEY, base_url=PROXYAPI_BASE_URL)
    response = client.chat.completions.create(
        model="qwen/qwen3.7-flash",
        messages=[{"role": "user", "content": prompt}]
    )
    answer = response.choices[0].message.content
    print(f"\n=== ОТВЕТ QWEN ПО GAZP (с новостями) ===\n{answer}")
else:
    print("Нет релевантных новостей для GAZP")