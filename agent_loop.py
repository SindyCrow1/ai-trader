import schedule
import time
import subprocess
from datetime import datetime

# ============ НАСТРОЙКИ ВРЕМЕНИ ТОРГОВ ============
TRADE_START_HOUR = 9      # С 9:00 (начало основной сессии)
TRADE_END_HOUR = 23       # До 23:00 (конец вечерней сессии)

def is_trading_hours():
    """Проверяет, открыта ли биржа прямо сейчас"""
    now = datetime.now()
    # Суббота (5) и воскресенье (6) — биржа закрыта
    if now.weekday() >= 5:
        return False
    # Биржа работает с 9:00 до 23:00
    if TRADE_START_HOUR <= now.hour < TRADE_END_HOUR:
        return True
    return False

def run_agent():
    now_str = datetime.now().strftime('%H:%M:%S')
    
    if not is_trading_hours():
        print(f"[{now_str}] Биржа закрыта — пропускаем запуск")
        return
    
    print(f"\n[{now_str}] Запуск агента...")
    result = subprocess.run(
        ["py", "agent_v9.py"],
        cwd="C:\\ai_trader",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if result.stdout:
        lines = result.stdout.strip().split("\n")
        for line in lines[-5:]:
            print(line)
    if result.stderr:
        print(f"Ошибка: {result.stderr[:200]}")

schedule.every(30).minutes.do(run_agent)

print("=" * 60)
print("АГЕНТ ЗАПУЩЕН В ЦИКЛИЧЕСКОМ РЕЖИМЕ")
print(f"Интервал: каждые 30 минут")
print(f"Торговля: только в часы работы биржи ({TRADE_START_HOUR}:00–{TRADE_END_HOUR}:00, Пн–Пт)")
print("Для остановки нажми Ctrl+C")
print("=" * 60)

# Первый запуск — только если биржа открыта
run_agent()

while True:
    schedule.run_pending()
    time.sleep(60)