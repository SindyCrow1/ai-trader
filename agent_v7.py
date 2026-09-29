import os
import json
import feedparser
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from t_tech.invest import Client, Quotation
from t_tech.invest.schemas import OrderDirection, CandleInterval


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

def calculate_rsi(prices, period=14):
    """RSI — индекс относительной силы"""
    if len(prices) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_ma(prices, period):
    """Скользящая средняя"""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

# ============================================================
# ШАГ 1: Данные о SBER + технический анализ
# ============================================================
log("=" * 60)
log("ЗАПУСК АГЕНТА v7 (Qwen + технический анализ)")
log("=" * 60)

with Client(INVEST_TOKEN) as client:
    last_price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
    last_price = last_price_resp.last_prices[0].price
    price_rub = last_price.units + last_price.nano / 1_000_000_000
    log(f"Цена SBER: {last_price.units} руб. {last_price.nano // 10**6} коп.")
    
    now = datetime.now()
    from_date = now - timedelta(days=60)
    
    # Дневные свечи за 60 дней
    candles_resp = client.market_data.get_candles(
        figi=SBER_FIGI, from_=from_date, to=now,
        interval=CandleInterval.CANDLE_INTERVAL_DAY
    )
    
    closes = []
    volumes = []
    for c in candles_resp.candles:
        closes.append(c.close.units + c.close.nano / 1_000_000_000)
        volumes.append(c.volume)
    
    log(f"Получено свечей: {len(closes)}")
    
    # Изменение за день
    if len(closes) >= 2:
        change_pct = ((closes[-1] - closes[-2]) / closes[-2]) * 100
        log(f"Изменение за день: {change_pct:+.2f}%")
    else:
        change_pct = 0.0
    
    # RSI
    rsi = calculate_rsi(closes, period=14)
    if rsi:
        log(f"RSI(14): {rsi:.1f}")
    
    # Скользящие средние
    ma20 = calculate_ma(closes, 20)
    ma50 = calculate_ma(closes, 50)
    if ma20:
        log(f"MA20: {ma20:.2f} руб.")
    if ma50:
        log(f"MA50: {ma50:.2f} руб.")
    
    # Объём
    if len(volumes) >= 2:
        avg_volume = sum(volumes[-20:]) / min(20, len(volumes))
        last_volume = volumes[-1]
        volume_ratio = last_volume / avg_volume if avg_volume > 0 else 1
        log(f"Объём: {last_volume:.0f} (к среднему: {volume_ratio:.2f}x)")

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
# ШАГ 3: Qwen с техническим анализом
# ============================================================
if not filtered_news:
    signal = {"action": "HOLD", "confidence": 0.5, "reason": "Нет релевантных новостей"}
else:
    news_text = "\n".join(filtered_news[:30])
    
    # Формируем технические данные для промпта
    tech_data = f"""
ТЕХНИЧЕСКИЙ АНАЛИЗ:
- Цена SBER: {last_price.units} руб. {last_price.nano // 10**6} коп.
- Изменение за день: {change_pct:+.2f}%
"""
    if rsi:
        tech_data += f"- RSI(14): {rsi:.1f}"
        if rsi < 30:
            tech_data += " (ПЕРЕПРОДАННОСТЬ — возможен отскок вверх)"
        elif rsi > 70:
            tech_data += " (ПЕРЕКУПЛЕННОСТЬ — возможен откат вниз)"
        tech_data += "\n"
    if ma20:
        tech_data += f"- MA20: {ma20:.2f} руб."
        if closes[-1] > ma20:
            tech_data += " (цена выше MA20 — краткосрочный восходящий тренд)\n"
        else:
            tech_data += " (цена ниже MA20 — краткосрочный нисходящий тренд)\n"
    if ma50:
        tech_data += f"- MA50: {ma50:.2f} руб.\n"
    if ma20 and ma50:
        if ma20 > ma50:
            tech_data += "- MA20 выше MA50 (золотой крест — долгосрочный восходящий тренд)\n"
        else:
            tech_data += "- MA20 ниже MA50 (мёртвый крест — долгосрочный нисходящий тренд)\n"
    if len(volumes) >= 2:
        tech_data += f"- Объём: {volume_ratio:.2f}x к среднему за 20 дней\n"
        if volume_ratio > 1.5:
            tech_data += "  (высокий объём — сильное движение)\n"
        elif volume_ratio < 0.5:
            tech_data += "  (низкий объём — слабое движение)\n"
    
    prompt = f"""Ты — торговый аналитик. Проанализируй ситуацию по Сбербанку.

{tech_data}

НОВОСТИ:
{news_text}

ЗАДАЧА:
Учти И технические индикаторы, И новости. Если RSI показывает перепроданность, 
а новости нейтральные — это может быть сигнал на покупку. Если RSI перекупленность, 
а новости негативные — сигнал на продажу.

Ответь СТРОГО в формате JSON:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование на русском (2-3 предложения, укажи что важнее — техника или новости)"
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
# ШАГ 4: Сделка
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