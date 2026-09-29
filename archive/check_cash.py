import os
from dotenv import load_dotenv
from t_tech.invest import Client

load_dotenv()
TOKEN = os.getenv("INVEST_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

with Client(TOKEN) as client:
    limits = client.sandbox.get_sandbox_withdraw_limits(account_id=ACCOUNT_ID)
    
    # Перебираем список money
    for money in limits.money:
        print(f"Валюта: {money.currency}, Доступно: {money.units} ед. + {money.nano} нано")