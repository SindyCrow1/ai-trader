import os
from dotenv import load_dotenv
from t_tech.invest import Client

load_dotenv()

TOKEN = os.getenv("INVEST_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

if not TOKEN or not ACCOUNT_ID:
    print("ОШИБКА: не найдены INVEST_TOKEN или ACCOUNT_ID в .env")
    exit(1)

print(f"Проверяем счёт: {ACCOUNT_ID}")
print("=" * 50)

with Client(TOKEN) as client:
    portfolio = client.sandbox.get_sandbox_portfolio(account_id=ACCOUNT_ID)
    
    print(f"Общая стоимость портфеля: {portfolio.total_amount_portfolio}")
    print(f"Свободные деньги: {portfolio.total_amount_currencies}")
    print(f"Акции: {portfolio.total_amount_shares}")
    print(f"Облигации: {portfolio.total_amount_bonds}")
    print(f"Позиций в портфеле: {len(portfolio.positions)}")