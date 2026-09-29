import os
from dotenv import load_dotenv
from t_tech.invest import Client

load_dotenv()
TOKEN = os.getenv("INVEST_TOKEN")

tickers = ["GAZP", "LKOH", "ROSN", "GMKN", "YNDX", "VTBR", "MTSS", "NVTK"]

with Client(TOKEN) as client:
    for ticker in tickers:
        try:
            instruments = client.instruments.find_instrument(query=ticker)
            found = False
            for inst in instruments.instruments:
                if inst.ticker == ticker and inst.class_code == "TQBR":
                    print(f"{ticker}: {inst.figi} — {inst.name}")
                    found = True
                    break
            if not found:
                print(f"{ticker}: не найден на TQBR")
        except Exception as e:
            print(f"{ticker}: ошибка — {e}")