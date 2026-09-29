with open("agent_log.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

signals = [line for line in lines if "СИГНАЛ" in line]

print(f"Всего сигналов: {len(signals)}")
print()

buy = [s for s in signals if "action=BUY" in s or "BUY |" in s]
sell = [s for s in signals if "action=SELL" in s or "SELL |" in s]
hold = [s for s in signals if "HOLD" in s]

print(f"BUY:  {len(buy)}")
print(f"SELL: {len(sell)}")
print(f"HOLD: {len(hold)}")