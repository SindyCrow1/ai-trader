import os
import json
import feedparser
from datetime import datetime, timedelta
from dotenv import load_dotenv
from gigachat import GigaChat
from t_tech.invest import Client, Quotation
from t_tech.invest.schemas import OrderDirection, CandleInterval

# Фикс кодировки для Windows
import sys
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")
INVEST_TOKEN = os.getenv("INVEST_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
SBER_FIGI = "BBG004730N88"
LOG_FILE = "agent_log.txt"

# Три источника новостей
SOURCES = {
    "РБК": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
    "Интерфакс": "https://www.interfax.ru/rss.asp",
    "Коммерсантъ": "https://www.kommersant.ru/RSS/news.xml",
}

KEYWORDS = [
    "сбер", "сбербанк", "банк", "банковск", "цб", "центробанк",
    "ставк", "ключев", "акци", "бирж", "рубл", "инфляц",
    "кредит", "ипотек", "вклад", "финанс"
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
log("ЗАПУСК АГЕНТА v5 (3 источника новостей)")
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
# ШАГ 2: Собираем новости из ВСЕХ источников
# ============================================================
all_news = []
for source_name, url in SOURCES.items():
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:50]:
            title = entry.title
            summary = getattr(entry, 'summary', '')[:200]
            all_news.append({
                "source": source_name,
                "title": title,
                "summary": summary
            })
        print(f"{source_name}: получено {len(feed.entries[:50])} новостей")
    except Exception as e:
        print(f"{source_name}: ошибка — {e}")

log(f"Всего новостей из всех источников: {len(all_news)}")

# Фильтруем по ключевым словам
filtered_news = []
for item in all_news:
    text_lower = (item["title"] + " " + item["summary"]).lower()
    if any(kw in text_lower for kw in KEYWORDS):
        filtered_news.append(f"[{item['source']}] {item['title']}\n  {item['summary']}")

log(f"После фильтра: {len(filtered_news)}")

# ============================================================
# ШАГ 3: GigaChat
# ============================================================
if not filtered_news:
    signal = {"action": "HOLD", "confidence": 0.5, "reason": "Нет релевантных новостей"}
else:
    # Ограничиваем до 30 новостей, чтобы не перегружать промпт
    news_text = "\n".join(filtered_news[:30])
    
    prompt = f"""Ты — торговый аналитик. Проанализируй ситуацию по Сбербанку.

ВАЖНО: анализируй ТОЛЬКО финансовые и корпоративные события.
Игнорируй политические новости, новости о власти и геополитике.
Если новость не касается финансов, банков или Сбербанка — пропусти её.

Цена SBER: {last_price.units} руб. {last_price.nano // 10**6} коп.
Изменение за день: {change_pct:+.2f}%

Релевантные новости из РБК, Интерфакса и Коммерсанта:
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
        print(f"\n=== СЫРОЙ ОТВЕТ GIGACHAT ===\n{answer}\n=== КОНЕЦ ОТВЕТА ===\n")
        
        start = answer.find("{")
        end = answer.rfind("}") + 1
        
        if start == -1 or end <= start:
            log(f"GigaChat вернул не JSON: {answer[:200]}")
            signal = {"action": "HOLD", "confidence": 0.5, "reason": "GigaChat не вернул JSON"}
        else:
            try:
                signal = json.loads(answer[start:end])
            except json.JSONDecodeError as e:
                log(f"Ошибка парсинга JSON: {e}")
                log(f"Ответ был: {answer[:500]}")
                signal = {"action": "HOLD", "confidence": 0.5, "reason": "Ошибка парсинга JSON"}

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