import csv

# ============ ПАРАМЕТРЫ ============
COMMISSION = 0.0005      # 0.05% комиссия брокера
SLIPPAGE = 0.001         # 0.1% проскальзывание
STOP_LOSS = 0.07         # 7% стоп-лосс
START_BALANCE = 1000000  # 1 млн руб.

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

def calculate_ma(prices, period):
    """Считает скользящую среднюю."""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

def backtest(candles, rsi_buy=30, rsi_sell=70, use_trend_filter=True):
    """
    Бэктест с фильтром тренда.
    use_trend_filter=True: покупаем только если MA20 > MA50 (восходящий тренд).
    """
    position = 0
    balance = START_BALANCE
    buy_price = 0
    trades = []
    equity_curve = []
    
    closes = []
    
    for candle in candles:
        closes.append(candle["close"])
        
        current_equity = balance + (position * candle["close"])
        equity_curve.append(current_equity)
        
        if len(closes) < 55:  # нужно для MA50
            continue
        
        rsi = calculate_rsi(closes, period=14)
        ma20 = calculate_ma(closes, 20)
        ma50 = calculate_ma(closes, 50)
        
        if rsi is None or ma20 is None or ma50 is None:
            continue
        
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
                    "rsi": rsi,
                    "pnl": revenue - buy_price,
                })
                position = 0
                continue
        
        # --- BUY ---
        if rsi < rsi_buy and position == 0:
            # ФИЛЬТР ТРЕНДА
            if use_trend_filter and ma20 <= ma50:
                # Тренд нисходящий — пропускаем
                continue
            
            buy_price = price * (1 + SLIPPAGE)
            cost = buy_price * (1 + COMMISSION)
            balance -= cost
            position = 1
            trades.append({
                "date": candle["begin"],
                "action": "BUY",
                "price": buy_price,
                "rsi": rsi,
                "pnl": None,
            })
        
        # --- SELL ---
        elif rsi > rsi_sell and position > 0:
            sell_price = price * (1 - SLIPPAGE)
            revenue = sell_price * (1 - COMMISSION)
            balance += revenue
            trades.append({
                "date": candle["begin"],
                "action": "SELL",
                "price": sell_price,
                "rsi": rsi,
                "pnl": revenue - buy_price,
            })
            position = 0
    
    # Если позиция осталась — продаём по последней цене
    if position > 0:
        sell_price = closes[-1] * (1 - SLIPPAGE)
        revenue = sell_price * (1 - COMMISSION)
        balance += revenue
        trades.append({
            "date": candles[-1]["begin"],
            "action": "SELL (final)",
            "price": sell_price,
            "rsi": None,
            "pnl": revenue - buy_price,
        })
    
    return trades, balance, equity_curve


def calculate_metrics(trades, equity_curve, final_balance):
    """Считает метрики."""
    closed_trades = [t for t in trades if t["pnl"] is not None]
    wins = [t for t in closed_trades if t["pnl"] > 0]
    win_rate = len(wins) / len(closed_trades) * 100 if closed_trades else 0
    
    max_equity = equity_curve[0]
    max_dd = 0
    for eq in equity_curve:
        if eq > max_equity:
            max_equity = eq
        dd = (max_equity - eq) / max_equity * 100
        if dd > max_dd:
            max_dd = dd
    
    total_return = (final_balance - START_BALANCE) / START_BALANCE * 100
    
    return {
        "win_rate": win_rate,
        "max_drawdown": max_dd,
        "total_return": total_return,
    }


if __name__ == "__main__":
    candles = load_csv("data/SBER_2025-01-01_2026-10-01.csv")
    print(f"Загружено свечей: {len(candles)}")
    
    print(f"\n=== БЕЗ ФИЛЬТРА ТРЕНДА ===")
    trades1, balance1, eq1 = backtest(candles, use_trend_filter=False)
    m1 = calculate_metrics(trades1, eq1, balance1)
    print(f"Сделок: {len(trades1)}")
    print(f"Доходность: {m1['total_return']:+.2f}%")
    print(f"Win rate: {m1['win_rate']:.1f}%")
    print(f"Max drawdown: {m1['max_drawdown']:.2f}%")
    
    print(f"\n=== С ФИЛЬТРОМ ТРЕНДА (MA20 > MA50) ===")
    trades2, balance2, eq2 = backtest(candles, use_trend_filter=True)
    m2 = calculate_metrics(trades2, eq2, balance2)
    print(f"Сделок: {len(trades2)}")
    print(f"Доходность: {m2['total_return']:+.2f}%")
    print(f"Win rate: {m2['win_rate']:.1f}%")
    print(f"Max drawdown: {m2['max_drawdown']:.2f}%")
    
    print(f"\n=== ВСЕ СДЕЛКИ (С ФИЛЬТРОМ) ===")
    for t in trades2:
        rsi_str = f"{t['rsi']:.1f}" if t['rsi'] is not None else "N/A"
        pnl_str = f"{t['pnl']:+.2f}" if t['pnl'] is not None else "—"
        print(f"{t['date'][:10]} | {t['action']:12} | {t['price']:.2f} руб. | RSI: {rsi_str:>5} | PnL: {pnl_str}")