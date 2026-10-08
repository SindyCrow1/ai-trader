import csv

def load_csv(filename):
    """Загружает свечи из CSV."""
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
    """Считает RSI по списку цен."""
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

def backtest(candles, rsi_buy=30, rsi_sell=70):
    """Простой бэктест: RSI < rsi_buy → BUY, RSI > rsi_sell → SELL."""
    position = 0
    balance = 1000000  # 1 млн руб.
    trades = []
    
    closes = []
    
    for i, candle in enumerate(candles):
        closes.append(candle["close"])
        
        if len(closes) < 15:
            continue
        
        rsi = calculate_rsi(closes, period=14)
        
        if rsi is None:
            continue
        
        price = candle["close"]
        
        # BUY
        if rsi < rsi_buy and position == 0:
            position = 1
            balance -= price
            trades.append({
                "date": candle["begin"],
                "action": "BUY",
                "price": price,
                "rsi": rsi,
            })
        
        # SELL
        elif rsi > rsi_sell and position > 0:
            position = 0
            balance += price
            trades.append({
                "date": candle["begin"],
                "action": "SELL",
                "price": price,
                "rsi": rsi,
            })
    
    # Если позиция осталась — продаём по последней цене
    if position > 0:
        balance += closes[-1]
        trades.append({
            "date": candles[-1]["begin"],
            "action": "SELL (final)",
            "price": closes[-1],
            "rsi": None,
        })
    
    return trades, balance


if __name__ == "__main__":
    candles = load_csv("data/SBER_2025-01-01_2026-10-01.csv")
    print(f"Загружено свечей: {len(candles)}")
    
    trades, final_balance = backtest(candles, rsi_buy=30, rsi_sell=70)
    
    print(f"\n=== РЕЗУЛЬТАТЫ БЭКТЕСТА ===")
    print(f"Сделок: {len(trades)}")
    print(f"Финальный баланс: {final_balance:.2f} руб.")
    print(f"Прибыль/убыток: {final_balance - 1000000:+.2f} руб.")
    print(f"Доходность: {((final_balance - 1000000) / 1000000) * 100:+.2f}%")
    
    print(f"\n=== ВСЕ СДЕЛКИ ===")
    for t in trades:
        rsi_str = f"{t['rsi']:.1f}" if t['rsi'] is not None else "N/A"
        print(f"{t['date'][:10]} | {t['action']:12} | {t['price']:.2f} руб. | RSI: {rsi_str}")