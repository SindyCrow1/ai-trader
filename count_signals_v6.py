import os

LOG_FILE = "agent_log.txt"

if not os.path.exists(LOG_FILE):
    print(f"Файл {LOG_FILE} не найден")
    exit(1)

with open(LOG_FILE, "r", encoding="utf-8") as f:
    lines = f.readlines()

signals = [line for line in lines if "СИГНАЛ:" in line]
runs = [line for line in lines if "ЗАПУСК АГЕНТА" in line]

print("=" * 60)
print(f"СТАТИСТИКА АГЕНТА")
print("=" * 60)
print(f"Всего циклов запуска: {len(runs)}")
print(f"Всего сигналов: {len(signals)}")
print()

buy = [s for s in signals if "СИГНАЛ: BUY" in s]
sell = [s for s in signals if "СИГНАЛ: SELL" in s]
hold = [s for s in signals if "СИГНАЛ: HOLD" in s]

print(f"BUY:  {len(buy)}")
print(f"SELL: {len(sell)}")
print(f"HOLD: {len(hold)}")
print()

if buy:
    print("=" * 60)
    print("BUY-СИГНАЛЫ:")
    print("=" * 60)
    for b in buy:
        print(b.strip())
    print()

if sell:
    print("=" * 60)
    print("SELL-СИГНАЛЫ:")
    print("=" * 60)
    for s in sell:
        print(s.strip())
    print()

if signals:
    print("=" * 60)
    print("ПОСЛЕДНИЕ 5 СИГНАЛОВ:")
    print("=" * 60)
    for s in signals[-5:]:
        print(s.strip())

# Проверяем, были ли реальные сделки
trades = [line for line in lines if "СДЕЛКА:" in line]
print()
print(f"Реальных сделок: {len(trades)}")
if trades:
    for t in trades:
        print(t.strip())