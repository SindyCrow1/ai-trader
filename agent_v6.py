import os
import json
import feedparser
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from t_tech.invest import Client, Quotation
from t_tech.invest.schemas import OrderDirection, CandleInterval

import sys
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

PROXYAPI_KEY = os.getenv("PROXYAPI_KEY")
PROXYAPI_BASE_URL = os.getenv("PROXYAPI_BASE_URL", "https://api.proxyapi.ru/v1")
QWEN_MODEL = "qwen/qwen3.7-flash"

INVEST_TOKEN = os.getenv("INVEST_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
SBER_FIGI = "BBG004730N88"
LOG_FILE = "agent_log.txt"

SOURCES = {
    "РБК": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
    "Интерфакс": "https://www.interfax.ru/rss.asp",
    "Коммерсантъ": "https://www.kommersant.ru/RSS/news.xml",
}

KEYWORDS = [
    "сбер", "сбербанк",
    "банковск", "банк", "цб", "центробанк",
    "ключев", "ставк",
    "кредит", "ипотек", "вклад",
    "дивиденд", "прибыл", "убыток",
    "акци", "капитализац", "бирж",
    "отчетност", "санкц"
]

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ============================================================
# ШАГ 1: Данные о SBER
# ============================================================
log("=" * 60)
log("ЗАПУСК АГЕНТА v6 (Qwen через ProxyAPI)")
log("=" * 60)

with Client(INVEST_TOKEN) as client:
    last_price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
    last_price = last_price_resp.last_prices[0].price
    price_rub = last_price.units + last_price.nano / 1_000_000_000
    log(f"Цена SBER: {last_price.units} руб. {last_price.nano // 10**6} коп.")
    
    now = datetime.now()
    from_date = now - timedelta(days=2)
    candles_resp = client.market_data.get_candles(
        figi=SBER_FIGI, from_=from_date, to=now,
        interval=CandleInterval.CANDLE_INTERVAL_DAY
    )
    
    if len(candles_resp.candles) >= 2:
        prev_close = candles_resp.candles[-2].close
        prev_price = prev_close.units + prev_close.nano / 1_000_000_000
        change_pct = ((price_rub - prev_price) / prev_price) * 100
        log(f"Изменение за день: {change_pct:+.2f}%")
    else:
        change_pct = 0.0

# ============================================================
# ШАГ 2: Новости
# ============================================================
all_news = []
for source_name, url in SOURCES.items():
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:50]:
            title = entry.title
            summary = getattr(entry, 'summary', '')[:200]
            all_news.append({"source": source_name, "title": title, "summary": summary})
        print(f"{source_name}: получено {len(feed.entries[:50])} новостей")
    except Exception as e:
        print(f"{source_name}: ошибка — {e}")

log(f"Всего новостей: {len(all_news)}")

filtered_news = []
for item in all_news:
    text_lower = (item["title"] + " " + item["summary"]).lower()
    if any(kw in text_lower for kw in KEYWORDS):
        filtered_news.append(f"[{item['source']}] {item['title']}\n  {item['summary']}")

log(f"После фильтра: {len(filtered_news)}")

# ============================================================
# ШАГ 3: Qwen через ProxyAPI
# ============================================================
if not filtered_news:
    signal = {"action": "HOLD", "confidence": 0.5, "reason": "Нет релевантных новостей"}
else:
    news_text = "\n".join(filtered_news[:30])
    
    prompt = f"""Ты — торговый аналитик. Проанализируй ситуацию по Сбербанку.

Цена SBER: {last_price.units} руб. {last_price.nano // 10**6} коп.
Изменение за день: {change_pct:+.2f}%

Релевантные новости:
{news_text}

Ответь СТРОГО в формате JSON:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование на русском"
}}
"""
    
    client = OpenAI(api_key=PROXYAPI_KEY, base_url=PROXYAPI_BASE_URL)
    
    try:
        response = client.chat.completions.create(
            model=QWEN_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content
        print(f"\n=== СЫРОЙ ОТВЕТ QWEN ===\n{answer}\n=== КОНЕЦ ОТВЕТА ===\n")
        
        start = answer.find("{")
        end = answer.rfind("}") + 1
        
        if start == -1 or end <= start:
            log(f"Qwen вернул не JSON: {answer[:200]}")
            signal = {"action": "HOLD", "confidence": 0.5, "reason": "Qwen не вернул JSON"}
        else:
            try:
                signal = json.loads(answer[start:end])
            except json.JSONDecodeError as e:
                log(f"Ошибка парсинга JSON: {e}")
                signal = {"action": "HOLD", "confidence": 0.5, "reason": "Ошибка парсинга JSON"}
    except Exception as e:
        log(f"Ошибка запроса к Qwen: {e}")
        signal = {"action": "HOLD", "confidence": 0.5, "reason": "Ошибка API"}

log(f"СИГНАЛ: {signal['action']} | confidence={signal['confidence']} | {signal['reason']}")

# ============================================================
# ШАГ 4: Сделка (порог 0.6)
# ============================================================
if signal['action'] == 'BUY' and signal['confidence'] >= 0.6:
    with Client(INVEST_TOKEN) as client:
        price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
        price = price_resp.last_prices[0].price
        order = client.sandbox.post_sandbox_order(
            account_id=ACCOUNT_ID, figi=SBER_FIGI, quantity=1,
            price=Quotation(units=price.units, nano=price.nano),
            direction=OrderDirection.ORDER_DIRECTION_BUY, order_type=1
        )
        log(f"СДЕЛКА: куплена 1 акция SBER, order_id={order.order_id}")
else:
    log(f"Сделка не выполнена (action={signal['action']}, confidence={signal['confidence']})")

log("Агент завершил работу")