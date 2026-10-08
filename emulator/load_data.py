import requests
import csv

def load_candles(ticker="SBER", board="TQBR", start_date="2025-01-01", end_date="2026-10-01"):
    url = (
        f"https://iss.moex.com/iss/engines/stock/markets/shares/"
        f"boards/{board}/securities/{ticker}/candles.json"
    )
    
    params = {
        "from": start_date,
        "till": end_date,
        "interval": 24,
    }
    
    print(f"Загружаем {ticker} с {start_date} по {end_date}...")
    
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"Ошибка: {response.status_code}")
        return []
    
    data = response.json()
    
    candles = data.get("candles", {})
    columns = candles.get("columns", [])
    rows = candles.get("data", [])
    
    if not rows:
        print("Нет данных за указанный период.")
        return []
    
    print(f"Получено {len(rows)} свечей.")
    print(f"Колонки: {columns}")
    
    filename = f"data/{ticker}_{start_date}_{end_date}.csv"
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    
    print(f"Сохранено в {filename}")
    
    return rows


if __name__ == "__main__":
    load_candles(
        ticker="SBER",
        board="TQBR",
        start_date="2025-01-01",
        end_date="2026-10-01"
    )