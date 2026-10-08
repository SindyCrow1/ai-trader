import csv
import json
import os
import time
from dotenv import load_dotenv
from openai import OpenAI

# Загружаем ключи из .env (из родительской папки)
load_dotenv("../.env")

PROXYAPI_KEY = os.getenv("PROXYAPI_KEY")
PROXYAPI_BASE_URL = os.getenv("PROXYAPI_BASE_URL", "https://api.proxyapi.ru/v1")
QWEN_MODEL = "qwen/qwen3.7-flash"

# ============ ПАРАМЕТРЫ ============
COMMISSION = 0.0005
SLIPPAGE = 0.001
STOP_LOSS = 0.07
START_BALANCE = 1000000
STEP = 20  # Запрос к Qwen каждые 20 свечей

def load_csv(filename):
    candles = []
    with open(filename, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            candles.append({
                "open": float(row["open"]),
                "close": float(row["close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "volume": int(row["volume"]),
                "begin": row["begin"],
            })
    return candles

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

def ask_qwen(price, rsi, ma20, ma50, volume_ratio, position):
    """Отправляет данные в Qwen и получает сигнал."""
    
    prompt = f"""Ты — торговый аналитик. Проанализируй ситуацию по акции SBER.

ТЕХНИЧЕСКИЕ ДАННЫЕ:
- Цена: {price:.2f} руб.
- RSI(14): {rsi:.1f}
- MA20: {ma20:.2f} руб.
- MA50: {ma50:.2f} руб.
- Объём к среднему: {volume_ratio:.2f}x
- Текущая позиция: {position} акций

Ответь СТРОГО в формате JSON:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование на русском"
}}
"""
    
    prompt = prompt.encode("utf-8", errors="ignore").decode("utf-8")
    
    client = OpenAI(api_key=PROXYAPI_KEY, base_url=PROXYAPI_BASE_URL)
    
    try:
        response = client.chat.completions.create(
            model=QWEN_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content
        
        start = answer.find("{")
        end = answer.rfind("}") + 1
        
        if start == -1 or end <= start:
            return {"action": "HOLD", "confidence": 0.5, "reason": "Нет JSON"}
        
        return json.loads(answer[start:end])
    except Exception as e:
        return {"action": "HOLD", "confidence": 0.5, "reason": f"Ошибка: {e}"}


def backtest_qwen(candles):
    """Бэктест с Qwen."""
    position = 0
    balance = START_BALANCE
    buy_price = 0
    trades = []
    equity_curve = []
    
    closes = []
    volumes = []
    
    for i, candle in enumerate(candles):
        closes.append(candle["close"])
        volumes.append(candle["volume"])
        
        current_equity = balance + (position * candle["close"])
        equity_curve.append(current_equity)
        
        if len(closes) < 55:
            continue
        
        # Запрос к Qwen каждые STEP свечей
        if i % STEP != 0:
            continue
        
        rsi = calculate_rsi(closes, period=14)
        ma20 = calculate_ma(closes, 20)
        ma50 = calculate_ma(closes, 50)
        
        if rsi is None or ma20 is None or ma50 is None:
            continue
        
        avg_volume = sum(volumes[-20:]) / 20
        volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1
        
        price = candle["close"]
        
        # --- СТОП-ЛОСС ---
        if position > 0:
            loss_pct = ((price - buy_price) / buy_price) * 100
            if loss_pct <= -STOP_LOSS * 100:
                sell_price = price * (1 - SLIPPAGE)
                revenue = sell_price * (1 - COMMISSION)
                balance += revenue
                trades.append({
                    "date": candle["begin"],
                    "action": "STOP-LOSS",
                    "price": sell_price,
                    "pnl": revenue - buy_price,
                })
                position = 0
                continue
        
        # --- QWEN ---
        signal = ask_qwen(price, rsi, ma20, ma50, volume_ratio, position)
        
        print(f"{candle['begin'][:10]} | RSI: {rsi:.1f} | {signal['action']} | {signal['reason'][:60]}")
        
        # --- BUY ---
        if signal['action'] == 'BUY' and signal['confidence'] >= 0.6 and position == 0:
            buy_price = price * (1 + SLIPPAGE)
            cost = buy_price * (1 + COMMISSION)
            balance -= cost
            position = 1
            trades.append({
                "date": candle["begin"],
                "action": "BUY",
                "price": buy_price,
                "pnl": None,
            })
        
        # --- SELL ---
        elif signal['action'] == 'SELL' and signal['confidence'] >= 0.6 and position > 0:
            sell_price = price * (1 - SLIPPAGE)
            revenue = sell_price * (1 - COMMISSION)
            balance += revenue
            trades.append({
                "date": candle["begin"],
                "action": "SELL",
                "price": sell_price,
                "pnl": revenue - buy_price,
            })
            position = 0
        
        time.sleep(1.5)  # Пауза между запросами
    
    # Закрываем позицию
    if position > 0:
        sell_price = closes[-1] * (1 - SLIPPAGE)
        revenue = sell_price * (1 - COMMISSION)
        balance += revenue
        trades.append({
            "date": candles[-1]["begin"],
            "action": "SELL (final)",
            "price": sell_price,
            "pnl": revenue - buy_price,
        })
    
    return trades, balance, equity_curve


if __name__ == "__main__":
    candles = load_csv("data/SBER_2025-01-01_2026-10-01.csv")
    print(f"Загружено свечей: {len(candles)}")
    print(f"Запросов к Qwen: ~{len(candles) // STEP}")
    print()
    
    trades, final_balance, equity_curve = backtest_qwen(candles)
    
    closed_trades = [t for t in trades if t["pnl"] is not None]
    wins = [t for t in closed_trades if t["pnl"] > 0]
    win_rate = len(wins) / len(closed_trades) * 100 if closed_trades else 0
    
    print(f"\n=== РЕЗУЛЬТАТЫ (QWEN) ===")
    print(f"Сделок: {len(trades)}")
    print(f"Финальный баланс: {final_balance:.2f} руб.")
    print(f"Прибыль/убыток: {final_balance - START_BALANCE:+.2f} руб.")
    print(f"Доходность: {((final_balance - START_BALANCE) / START_BALANCE) * 100:+.2f}%")
    print(f"Win rate: {win_rate:.1f}%")
    
    print(f"\n=== ВСЕ СДЕЛКИ ===")
    for t in trades:
        pnl_str = f"{t['pnl']:+.2f}" if t['pnl'] is not None else "—"
        print(f"{t['date'][:10]} | {t['action']:12} | {t['price']:.2f} руб. | PnL: {pnl_str}")