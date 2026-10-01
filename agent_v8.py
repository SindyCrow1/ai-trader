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
TRADES_FILE = "trades_log.txt"

# ============ РИСК-МЕНЕДЖМЕНТ ============
MAX_POSITION = 5          # Максимум 5 акций SBER
MAX_TRADES_PER_DAY = 2    # Максимум 2 сделки в день
STOP_LOSS_PERCENT = 5.0   # Стоп-лосс 5%
TRADE_START_HOUR = 9      # С 9:00
TRADE_END_HOUR = 23       # До 23:00

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

def log_trade(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    with open(TRADES_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def is_trading_hours():
    now = datetime.now()
    if now.weekday() >= 5:  # Сб, Вс
        return False
    if TRADE_START_HOUR <= now.hour < TRADE_END_HOUR:
        return True
    return False

def get_today_trades_count():
    today = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(TRADES_FILE):
        return 0
    count = 0
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if today in line and ("КУПЛЕНО" in line or "ПРОДАНО" in line):
                count += 1
    return count

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        if diff > 0:
            gains.append(diff); losses.append(0)
        else:
            gains.append(0); losses.append(abs(diff))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ma(prices, period):
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

# ============================================================
# ШАГ 1: Данные о SBER + позиция
# ============================================================
log("=" * 60)
log("ЗАПУСК АГЕНТА v8 (Qwen + тех.анализ + риск-менеджмент)")
log("=" * 60)

with Client(INVEST_TOKEN) as client:
    portfolio = client.sandbox.get_sandbox_portfolio(account_id=ACCOUNT_ID)
    
    sber_position = 0
    sber_avg_price = 0
    for pos in portfolio.positions:
        if pos.figi == SBER_FIGI:
            sber_position = int(pos.quantity.units)
            if sber_position > 0:
                sber_avg_price = (pos.average_position_price.units + 
                                   pos.average_position_price.nano / 1_000_000_000)
            break
    
    log(f"Текущая позиция SBER: {sber_position} акций")
    if sber_position > 0:
        log(f"Средняя цена покупки: {sber_avg_price:.2f} руб.")
    
    last_price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
    last_price = last_price_resp.last_prices[0].price
    price_rub = last_price.units + last_price.nano / 1_000_000_000
    log(f"Цена SBER: {last_price.units} руб. {last_price.nano // 10**6} коп.")
    
    now = datetime.now()
    from_date = now - timedelta(days=60)
    candles_resp = client.market_data.get_candles(
        figi=SBER_FIGI, from_=from_date, to=now,
        interval=CandleInterval.CANDLE_INTERVAL_DAY
    )
    
    closes = [c.close.units + c.close.nano / 1_000_000_000 for c in candles_resp.candles]
    volumes = [c.volume for c in candles_resp.candles]
    
    if len(closes) >= 2:
        change_pct = ((closes[-1] - closes[-2]) / closes[-2]) * 100
        log(f"Изменение за день: {change_pct:+.2f}%")
    else:
        change_pct = 0.0
    
    rsi = calculate_rsi(closes, period=14)
    ma20 = calculate_ma(closes, 20)
    ma50 = calculate_ma(closes, 50)
    
    if rsi: log(f"RSI(14): {rsi:.1f}")
    if ma20: log(f"MA20: {ma20:.2f} руб.")
    if ma50: log(f"MA50: {ma50:.2f} руб.")
    
    volume_ratio = 1.0
    if len(volumes) >= 20:
        avg_volume = sum(volumes[-20:]) / 20
        volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1
        log(f"Объём: {volumes[-1]:.0f} (к среднему: {volume_ratio:.2f}x)")

# ============================================================
# ПРОВЕРКА РИСК-МЕНЕДЖМЕНТА
# ============================================================
log("--- Проверка риск-менеджмента ---")

if not is_trading_hours():
    log("БИРЖА ЗАКРЫТА — сделки не выполняются")
    trading_allowed = False
else:
    log("Биржа открыта")
    trading_allowed = True

if sber_position >= MAX_POSITION:
    log(f"ЛИМИТ ПОЗИЦИИ: {sber_position}/{MAX_POSITION} — покупки запрещены")
    buying_allowed = False
else:
    log(f"Позиция: {sber_position}/{MAX_POSITION} — покупка разрешена")
    buying_allowed = True

today_trades = get_today_trades_count()
if today_trades >= MAX_TRADES_PER_DAY:
    log(f"ЛИМИТ СДЕЛОК: {today_trades}/{MAX_TRADES_PER_DAY} — сделки запрещены")
    buying_allowed = False
else:
    log(f"Сделок за сегодня: {today_trades}/{MAX_TRADES_PER_DAY}")

stop_loss_triggered = False
if sber_position > 0 and sber_avg_price > 0:
    loss_pct = ((price_rub - sber_avg_price) / sber_avg_price) * 100
    log(f"P&L по позиции: {loss_pct:+.2f}%")
    if loss_pct <= -STOP_LOSS_PERCENT:
        log(f"СТОП-ЛОСС: падение {loss_pct:.2f}% (порог -{STOP_LOSS_PERCENT}%)")
        stop_loss_triggered = True

# ============================================================
# ШАГ 2: Новости
# ============================================================
all_news = []
for source_name, url in SOURCES.items():
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:50]:
            all_news.append({
                "source": source_name,
                "title": entry.title,
                "summary": getattr(entry, 'summary', '')[:200]
            })
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
# ШАГ 3: Qwen
# ============================================================
if not filtered_news:
    signal = {"action": "HOLD", "confidence": 0.5, "reason": "Нет релевантных новостей"}
else:
    news_text = "\n".join(filtered_news[:30])
    
    tech_data = f"""
ТЕХНИЧЕСКИЙ АНАЛИЗ:
- Цена SBER: {last_price.units} руб. {last_price.nano // 10**6} коп.
- Изменение за день: {change_pct:+.2f}%
"""
    if rsi:
        tech_data += f"- RSI(14): {rsi:.1f}"
        if rsi < 30: tech_data += " (ПЕРЕПРОДАННОСТЬ)"
        elif rsi > 70: tech_data += " (ПЕРЕКУПЛЕННОСТЬ)"
        tech_data += "\n"
    if ma20: tech_data += f"- MA20: {ma20:.2f} руб.\n"
    if ma50: tech_data += f"- MA50: {ma50:.2f} руб.\n"
    if ma20 and ma50:
        if ma20 > ma50: tech_data += "- MA20 выше MA50 (восходящий тренд)\n"
        else: tech_data += "- MA20 ниже MA50 (нисходящий тренд)\n"
    if len(volumes) >= 20:
        tech_data += f"- Объём: {volume_ratio:.2f}x к среднему\n"
    
    position_context = f"""
ТЕКУЩАЯ ПОЗИЦИЯ:
- Акций SBER: {sber_position}
- Средняя цена покупки: {sber_avg_price:.2f} руб.
- Максимум разрешено: {MAX_POSITION}
"""
    
    prompt = f"""Ты — торговый аналитик. Проанализируй ситуацию по Сбербанку.

{tech_data}
{position_context}

НОВОСТИ:
{news_text}

ЗАДАЧА:
Учти технические индикаторы, новости и текущую позицию.
Если позиция уже большая — не рекомендуй новые покупки.

Ответь СТРОГО в формате JSON:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование на русском"
}}
"""
    # Очистка промпта от проблемных символов
    prompt = prompt.encode("utf-8", errors="ignore").decode("utf-8")

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
# ШАГ 4: Сделка с риск-менеджментом
# ============================================================

# 4.1. Стоп-лосс
if stop_loss_triggered and trading_allowed and sber_position > 0:
    log("ВЫПОЛНЯЕМ СТОП-ЛОСС")
    with Client(INVEST_TOKEN) as client:
        price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
        price = price_resp.last_prices[0].price
        order = client.sandbox.post_sandbox_order(
            account_id=ACCOUNT_ID, figi=SBER_FIGI, quantity=sber_position,
            price=Quotation(units=price.units, nano=price.nano),
            direction=OrderDirection.ORDER_DIRECTION_SELL, order_type=1
        )
        log_trade(f"ПРОДАНО {sber_position} акций SBER (стоп-лосс), order_id={order.order_id}")

# 4.2. Покупка
elif signal['action'] == 'BUY' and signal['confidence'] >= 0.6:
    if not trading_allowed:
        log("Сделка НЕ выполнена: биржа закрыта")
    elif not buying_allowed:
        log("Сделка НЕ выполнена: лимиты риск-менеджмента")
    else:
        log("ВЫПОЛНЯЕМ ПОКУПКУ")
        with Client(INVEST_TOKEN) as client:
            price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
            price = price_resp.last_prices[0].price
            order = client.sandbox.post_sandbox_order(
                account_id=ACCOUNT_ID, figi=SBER_FIGI, quantity=1,
                price=Quotation(units=price.units, nano=price.nano),
                direction=OrderDirection.ORDER_DIRECTION_BUY, order_type=1
            )
            log_trade(f"КУПЛЕНО 1 акция SBER по {price.units} руб., order_id={order.order_id}")

# 4.3. Продажа по сигналу
elif signal['action'] == 'SELL' and signal['confidence'] >= 0.6:
    if not trading_allowed:
        log("Сделка НЕ выполнена: биржа закрыта")
    elif sber_position == 0:
        log("Сделка НЕ выполнена: нет акций")
    else:
        log("ВЫПОЛНЯЕМ ПРОДАЖУ")
        with Client(INVEST_TOKEN) as client:
            price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
            price = price_resp.last_prices[0].price
            order = client.sandbox.post_sandbox_order(
                account_id=ACCOUNT_ID, figi=SBER_FIGI, quantity=sber_position,
                price=Quotation(units=price.units, nano=price.nano),
                direction=OrderDirection.ORDER_DIRECTION_SELL, order_type=1
            )
            log_trade(f"ПРОДАНО {sber_position} акций SBER по {price.units} руб., order_id={order.order_id}")

else:
    log(f"Сделка не выполнена (action={signal['action']}, confidence={signal['confidence']})")

log("Агент завершил работу")