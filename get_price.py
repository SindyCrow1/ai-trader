import os
from dotenv import load_dotenv
from t_tech.invest import Client

load_dotenv()
TOKEN = os.getenv("INVEST_TOKEN")

with Client(TOKEN) as client:
    # Получаем цену последней сделки для SBER (FIGI: BBG004730N88)
    response = client.market_data.get_last_prices(
        figi=["BBG004730N88"]
    )
    
    if response.last_prices:
        price = response.last_prices[0].price
        print(f"Цена SBER: {price.units} руб. {price.nano // 10**6} коп.")
    else:
        print("Не удалось получить цену")