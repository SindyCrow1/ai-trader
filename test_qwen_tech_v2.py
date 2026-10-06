import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from t_tech.invest import Client
from t_tech.invest.schemas import CandleInterval

load_dotenv()

PROXYAPI_KEY = os.getenv("PROXYAPI_KEY")
PROXYAPI_BASE_URL = os.getenv("PROXYAPI_BASE_URL", "https://api.proxyapi.ru/v1")
INVEST_TOKEN = os.getenv("INVEST_TOKEN")

# Акции для теста
STOCKS = [
    ("LKOH", "BBG004731032", "Лукойл"),
    ("ROSN", "BBG004731354", "Роснефть"),
    ("GMKN", "BBG004731489", "Норникель"),
    ("VTBR", "BBG004730ZJ9", "ВТБ"),
    ("MTSS", "BBG004S681W1", "МТС"),
]

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

client_openai = OpenAI(api_key=PROXYAPI_KEY, base_url=PROXYAPI_BASE_URL)

print("=" * 60)
print("ТЕСТ QWEN НА НОВЫХ АКЦИЯХ")
print("=" * 60)

with Client(INVEST_TOKEN) as client:
    for ticker, figi, name in STOCKS:
        print(f"\n{'=' * 60}")
        print(f"{ticker} ({name})")
        print(f"{'=' * 60}")
        
        try:
            last_price_resp = client.market_data.get_last_prices(figi=[figi])
            last_price = last_price_resp.last_prices[0].price
            price_rub = last_price.units + last_price.nano / 1_000_000_000
            
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
            
            rsi = calculate_rsi(closes, period=14)
            ma20 = calculate_ma(closes, 20)
            ma50 = calculate_ma(closes, 50)
            
            volume_ratio = 1.0
            if len(volumes) >= 20:
                avg_volume = sum(volumes[-20:]) / 20
                volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1
            
            print(f"Цена: {price_rub:.2f} руб.")
            print(f"Изменение: {change_pct:+.2f}%")
            print(f"RSI(14): {rsi:.1f}" if rsi else "RSI: N/A")
            print(f"MA20: {ma20:.2f}" if ma20 else "MA20: N/A")
            print(f"MA50: {ma50:.2f}" if ma50 else "MA50: N/A")
            print(f"Объём: {volume_ratio:.2f}x")
            
            tech_data = f"""Акция: {name} ({ticker})
Цена: {price_rub:.2f} руб.
Изменение за день: {change_pct:+.2f}%
RSI(14): {rsi:.1f}
MA20: {ma20:.2f}
MA50: {ma50:.2f}
Объём: {volume_ratio:.2f}x к среднему
"""
            
            prompt = f"""Проанализируй акцию на основе технических данных.

{tech_data}

Ответь СТРОГО в формате JSON:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование на русском"
}}
"""
            
            prompt = prompt.encode("utf-8", errors="ignore").decode("utf-8")
            
            response = client_openai.chat.completions.create(
                model="qwen/qwen3.7-flash",
                messages=[{"role": "user", "content": prompt}]
            )
            answer = response.choices[0].message.content
            print(f"\nОтвет Qwen:\n{answer[:400]}")
            
        except Exception as e:
            print(f"Ошибка: {e}")

print("\n" + "=" * 60)
print("ТЕСТ ЗАВЕРШЁН")
print("=" * 60)