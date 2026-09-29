import os
from dotenv import load_dotenv
from t_tech.invest import Client
from t_tech.invest.schemas import MoneyValue

load_dotenv()
TOKEN = os.getenv("INVEST_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

with Client(TOKEN) as client:
    # Пополняем счёт через MoneyValue
    result = client.sandbox.sandbox_pay_in(
        account_id=ACCOUNT_ID,
        amount=MoneyValue(currency="rub", units=1000000, nano=0)
    )
    print(f"Пополнение выполнено: {result}")