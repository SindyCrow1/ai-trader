import os
import json
import time
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
LOG_FILE = "agent_log.txt"
TRADES_FILE = "trades_log.txt"

# ============ СПИСОК АКЦИЙ ============
STOCKS = [
    {
        "ticker": "SBER",
        "figi": "BBG004730N88",
        "name": "Сбербанк",
        "max_position": 5,
    },
    
]

# ============ РИСК-МЕНЕДЖМЕНТ (общий) ============
MAX_TRADES_PER_DAY = 1
STOP_LOSS_PERCENT = 5.0
TRADE_START_HOUR = 9
TRADE_END_HOUR = 23

SOURCES = {
    "РБК": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
    "Интерфакс": "https://www.interfax.ru/rss.asp",
    "Коммерсантъ": "https://www.kommersant.ru/RSS/news.xml",
}

# Ключевые слова для фильтрации по каждой акции
KEYWORDS = {
    "SBER": ["сбер", "сбербанк", "банковск", "банк", "цб", "центробанк",
             "ключев", "ставк", "кредит", "ипотек", "вклад",
             "дивиденд", "прибыл", "убыток", "отчетност"],
}

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("cp1251", errors="replace").decode("cp1251"))
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def log_trade(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    with open(TRADES_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def is_trading_hours():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    if TRADE_START_HOUR <= now.hour < TRADE_END_HOUR:
        return True
    return False

def get_today_trades_count(ticker=None):
    today = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(TRADES_FILE):
        return 0
    count = 0
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if today in line and ("КУПЛЕНО" in line or "ПРОДАНО" in line):
                if ticker is None or ticker in line:
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

def process_stock(client, stock, all_news):
    """Обрабатывает одну акцию: данные, новости, Qwen, сделка"""
    ticker = stock["ticker"]
    figi = stock["figi"]
    name = stock["name"]
    max_position = stock["max_position"]
    
    log("=" * 60)
    log(f"ОБРАБОТКА {ticker} ({name})")
    log("=" * 60)
    
    # --- Позиция ---
    portfolio = client.sandbox.get_sandbox_portfolio(account_id=ACCOUNT_ID)
    position = 0
    avg_price = 0
    if portfolio.positions:
        for pos in portfolio.positions:
            if pos.figi == figi:
                if pos.quantity and pos.quantity.units is not None:
                    position = int(pos.quantity.units)
                    if position > 0 and pos.average_position_price:
                        avg_price = (pos.average_position_price.units + 
                                     pos.average_position_price.nano / 1_000_000_000)
                break
    
    log(f"Текущая позиция {ticker}: {position} акций")
    if position > 0:
        log(f"Средняя цена покупки: {avg_price:.2f} руб.")
    
    # --- Цена и свечи ---
    last_price_resp = client.market_data.get_last_prices(figi=[figi])
    last_price = last_price_resp.last_prices[0].price
    price_rub = last_price.units + last_price.nano / 1_000_000_000
    log(f"Цена {ticker}: {last_price.units} руб. {last_price.nano // 10**6} коп.")
    
    now = datetime.now()
    from_date = now - timedelta(days=60)
    candles_resp = client.market_data.get_candles(
        figi=figi, from_=from_date, to=now,
        interval=CandleInterval.CANDLE_INTERVAL_DAY
    )
    
    closes = [c.close.units + c.close.nano / 1_000_000_000 for c in candles_resp.candles]
    volumes = [c.volume for c in candles_resp.candles]
    
    change_pct = 0.0
    if len(closes) >= 2:
        change_pct = ((closes[-1] - closes[-2]) / closes[-2]) * 100
        log(f"Изменение за день: {change_pct:+.2f}%")
    
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
    
    # --- Риск-менеджмент ---
    log("--- Проверка риск-менеджмента ---")
    
    if not is_trading_hours():
        log("БИРЖА ЗАКРЫТА — сделки не выполняются")
        trading_allowed = False
    else:
        log("Биржа открыта")
        trading_allowed = True
    
    if position >= max_position:
        log(f"ЛИМИТ ПОЗИЦИИ: {position}/{max_position} — покупки запрещены")
        buying_allowed = False
    else:
        log(f"Позиция: {position}/{max_position} — покупка разрешена")
        buying_allowed = True
    
    today_trades = get_today_trades_count(ticker)
    if today_trades >= MAX_TRADES_PER_DAY:
        log(f"ЛИМИТ СДЕЛОК: {today_trades}/{MAX_TRADES_PER_DAY} — сделки запрещены")
        buying_allowed = False
    else:
        log(f"Сделок за сегодня: {today_trades}/{MAX_TRADES_PER_DAY}")
    
    stop_loss_triggered = False
    if position > 0 and avg_price > 0:
        loss_pct = ((price_rub - avg_price) / avg_price) * 100
        log(f"P&L по позиции: {loss_pct:+.2f}%")
        if loss_pct <= -STOP_LOSS_PERCENT:
            log(f"СТОП-ЛОСС: падение {loss_pct:.2f}% (порог -{STOP_LOSS_PERCENT}%)")
            stop_loss_triggered = True
    
    # --- Новости ---
    keywords = KEYWORDS.get(ticker, [])
    filtered_news = []
    for item in all_news:
        text_lower = (item["title"] + " " + item["summary"]).lower()
        if any(kw in text_lower for kw in keywords):
            filtered_news.append(f"[{item['source']}] {item['title']}\n  {item['summary']}")
    
    log(f"Новостей после фильтра: {len(filtered_news)}")
    
    # --- Qwen ---
    if not filtered_news:
        signal = {"action": "HOLD", "confidence": 0.5, "reason": "Нет релевантных новостей"}
    else:
        news_text = "\n".join(filtered_news[:30])
        
        tech_data = f"""
ТЕХНИЧЕСКИЙ АНАЛИЗ:
- Акция: {name} ({ticker})
- Цена: {last_price.units} руб. {last_price.nano // 10**6} коп.
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
- Акций {ticker}: {position}
- Средняя цена покупки: {avg_price:.2f} руб.
- Максимум разрешено: {max_position}
"""
        
        prompt = f"""Ты — торговый аналитик. Проанализируй ситуацию по акции {name} ({ticker}).

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
        
        prompt = prompt.encode("utf-8", errors="ignore").decode("utf-8")
        
        client_openai = OpenAI(api_key=PROXYAPI_KEY, base_url=PROXYAPI_BASE_URL)
        
        try:
            response = client_openai.chat.completions.create(
                model=QWEN_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            answer = response.choices[0].message.content
            print(f"\n=== СЫРОЙ ОТВЕТ QWEN ({ticker}) ===\n{answer}\n=== КОНЕЦ ОТВЕТА ===\n")
            
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
    
    log(f"СИГНАЛ {ticker}: {signal['action']} | confidence={signal['confidence']} | {signal['reason']}")
    
    # --- Сделка ---
    if stop_loss_triggered and trading_allowed and position > 0:
        log(f"ВЫПОЛНЯЕМ СТОП-ЛОСС по {ticker}")
        price_resp = client.market_data.get_last_prices(figi=[figi])
        price = price_resp.last_prices[0].price
        order = client.sandbox.post_sandbox_order(
            account_id=ACCOUNT_ID, figi=figi, quantity=position,
            price=Quotation(units=price.units, nano=price.nano),
            direction=OrderDirection.ORDER_DIRECTION_SELL, order_type=1
        )
        log_trade(f"ПРОДАНО {position} акций {ticker} (стоп-лосс), order_id={order.order_id}")
    
    elif signal['action'] == 'BUY' and signal['confidence'] >= 0.6:
        if not trading_allowed:
            log(f"Сделка по {ticker} НЕ выполнена: биржа закрыта")
        elif not buying_allowed:
            log(f"Сделка по {ticker} НЕ выполнена: лимиты риск-менеджмента")
        else:
            log(f"ВЫПОЛНЯЕМ ПОКУПКУ {ticker}")
            price_resp = client.market_data.get_last_prices(figi=[figi])
            price = price_resp.last_prices[0].price
            order = client.sandbox.post_sandbox_order(
                account_id=ACCOUNT_ID, figi=figi, quantity=1,
                price=Quotation(units=price.units, nano=price.nano),
                direction=OrderDirection.ORDER_DIRECTION_BUY, order_type=1
            )
            log_trade(f"КУПЛЕНО 1 акция {ticker} по {price.units} руб., order_id={order.order_id}")
            
            # Ждём, пока песочница обновит позицию
            time.sleep(5)
            
            # Перепроверяем позицию
            portfolio_check = client.sandbox.get_sandbox_portfolio(account_id=ACCOUNT_ID)
            new_position = 0
            if portfolio_check.positions:
                for pos in portfolio_check.positions:
                    if pos.figi == figi:
                        if pos.quantity and pos.quantity.units is not None:
                            new_position = int(pos.quantity.units)
                        break
            log(f"Позиция {ticker} после покупки: {new_position} акций")
    
    elif signal['action'] == 'SELL' and signal['confidence'] >= 0.6:
        if not trading_allowed:
            log(f"Сделка по {ticker} НЕ выполнена: биржа закрыта")
        elif position == 0:
            log(f"Сделка по {ticker} НЕ выполнена: нет акций")
        else:
            log(f"ВЫПОЛНЯЕМ ПРОДАЖУ {ticker}")
            price_resp = client.market_data.get_last_prices(figi=[figi])
            price = price_resp.last_prices[0].price
            order = client.sandbox.post_sandbox_order(
                account_id=ACCOUNT_ID, figi=figi, quantity=position,
                price=Quotation(units=price.units, nano=price.nano),
                direction=OrderDirection.ORDER_DIRECTION_SELL, order_type=1
            )
            log_trade(f"ПРОДАНО {position} акций {ticker} по {price.units} руб., order_id={order.order_id}")
    
    else:
        log(f"Сделка по {ticker} не выполнена (action={signal['action']}, confidence={signal['confidence']})")


# ============================================================
# ГЛАВНЫЙ ЦИКЛ
# ============================================================
log("=" * 60)
log("ЗАПУСК АГЕНТА v9 (SBER)")
log("=" * 60)

# Собираем новости один раз для всех акций
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
        print(f"{source_name}: получено {len(feed.entries[:50])} новостей")
    except Exception as e:
        print(f"{source_name}: ошибка — {e}")

log(f"Всего новостей: {len(all_news)}")

# Обрабатываем каждую акцию
with Client(INVEST_TOKEN) as client:
    for stock in STOCKS:
        process_stock(client, stock, all_news)

log("Агент завершил работу")