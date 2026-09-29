import os
import json
import feedparser
import sys
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime, timedelta
from dotenv import load_dotenv
from gigachat import GigaChat
from t_tech.invest import Client, Quotation
from t_tech.invest.schemas import OrderDirection, CandleInterval

load_dotenv()

AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")
INVEST_TOKEN = os.getenv("INVEST_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
SBER_FIGI = "BBG004730N88"
LOG_FILE = "agent_log.txt"

KEYWORDS = [
    "сбер", "сбербанк", "банк", "банковск", "цб", "центробанк",
    "ставк", "ключев", "акци", "бирж", "санкц", "рубл", "инфляц",
    "кредит", "ипотек", "вклад", "финанс", "мобилизац", "балтик"
]

def log(message):
    """Записывает сообщение в лог-файл с временной меткой"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ============================================================
# ШАГ 1: Данные о SBER
# ============================================================
log("=" * 60)
log("ЗАПУСК АГЕНТА v4")
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
# ШАГ 2: RSS и фильтр
# ============================================================
url = "https://rssexport.rbc.ru/rbcnews/news/30/full.rss"
feed = feedparser.parse(url)
all_news = feed.entries[:30]
filtered_news = []

for entry in all_news:
    title_lower = entry.title.lower()
    summary = getattr(entry, 'summary', '')[:200]
    text_lower = (title_lower + " " + summary.lower())
    if any(kw in text_lower for kw in KEYWORDS):
        filtered_news.append(f"- {entry.title}\n  {summary}")

log(f"Новостей всего: {len(all_news)}, после фильтра: {len(filtered_news)}")

# ============================================================
# ШАГ 3: GigaChat
# ============================================================
if not filtered_news:
    signal = {"action": "HOLD", "confidence": 0.5, "reason": "Нет релевантных новостей"}
else:
    news_text = "\n".join(filtered_news)
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
    
    with GigaChat(credentials=AUTH_KEY, verify_ssl_certs=False, model="GigaChat-3-Ultra") as giga:
        response = giga.chat(prompt)
        answer = response.choices[0].message.content
        start = answer.find("{")
        end = answer.rfind("}") + 1
        signal = json.loads(answer[start:end])

log(f"СИГНАЛ: {signal['action']} | confidence={signal['confidence']} | {signal['reason']}")

# ============================================================
# ШАГ 4: Сделка
# ============================================================
if signal['action'] == 'BUY' and signal['confidence'] >= 0.7:
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
    log(f"Сделка не выполнена (action={signal['action']})")

log("Агент завершил работу")