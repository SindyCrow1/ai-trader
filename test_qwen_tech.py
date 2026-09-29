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

# Акции для теста (тикер, FIGI, название)
STOCKS = [
    ("SBER", "BBG004730N88", "Сбербанк"),
    ("GAZP", "BBG004730RP0", "Газпром"),
    ("LKOH", "BBG004731032", "Лукойл"),
    ("ROSN", "BBG004731354", "Роснефть"),
    ("GMKN", "BBG004731489", "Норникель"),
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

def get_stock_data(client, figi):
    """Собирает технические данные по акции"""
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
    
    return {
        "price": price_rub,
        "change_pct": change_pct,
        "rsi": rsi,
        "ma20": ma20,
        "ma50": ma50,
        "volume_ratio": volume_ratio,
    }

client_openai = OpenAI(api_key=PROXYAPI_KEY, base_url=PROXYAPI_BASE_URL)

print("=" * 60)
print("ТЕСТ QWEN НА РАЗНЫХ АКЦИЯХ (с техническими данными)")
print("=" * 60)

with Client(INVEST_TOKEN) as client:
    for ticker, figi, name in STOCKS:
        print(f"\n{'=' * 60}")
        print(f"{ticker} ({name})")
        print(f"{'=' * 60}")
        
        try:
            data = get_stock_data(client, figi)
        except Exception as e:
            print(f"Ошибка получения данных: {e}")
            continue
        
        print(f"Цена: {data['price']:.2f} руб.")
        print(f"Изменение за день: {data['change_pct']:+.2f}%")
        if data['rsi']:
            print(f"RSI(14): {data['rsi']:.1f}")
        if data['ma20']:
            print(f"MA20: {data['ma20']:.2f}")
        if data['ma50']:
            print(f"MA50: {data['ma50']:.2f}")
        print(f"Объём: {data['volume_ratio']:.2f}x к среднему")
        
        # Формируем промпт с техническими данными
        tech_data = f"""Акция: {name} ({ticker})
Цена: {data['price']:.2f} руб.
Изменение за день: {data['change_pct']:+.2f}%
"""
        if data['rsi']:
            tech_data += f"RSI(14): {data['rsi']:.1f}"
            if data['rsi'] < 30: tech_data += " (ПЕРЕПРОДАННОСТЬ)"
            elif data['rsi'] > 70: tech_data += " (ПЕРЕКУПЛЕННОСТЬ)"
            tech_data += "\n"
        if data['ma20']: tech_data += f"MA20: {data['ma20']:.2f}\n"
        if data['ma50']: tech_data += f"MA50: {data['ma50']:.2f}\n"
        if data['ma20'] and data['ma50']:
            if data['ma20'] > data['ma50']:
                tech_data += "MA20 > MA50 (восходящий тренд)\n"
            else:
                tech_data += "MA20 < MA50 (нисходящий тренд)\n"
        tech_data += f"Объём: {data['volume_ratio']:.2f}x к среднему\n"
        
        prompt = f"""Ты — торговый аналитик. Проанализируй акцию на основе технических данных.

{tech_data}

Ответь СТРОГО в формате JSON:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование на русском"
}}
"""
        
        try:
            response = client_openai.chat.completions.create(
                model="qwen/qwen3.7-flash",
                messages=[{"role": "user", "content": prompt}]
            )
            answer = response.choices[0].message.content
            print(f"\nОтвет Qwen:\n{answer[:500]}")
        except Exception as e:
            print(f"Ошибка Qwen: {e}")

print("\n" + "=" * 60)
print("ТЕСТ ЗАВЕРШЁН")
print("=" * 60)