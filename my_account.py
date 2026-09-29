import os
from dotenv import load_dotenv
from t_tech.invest import Client

load_dotenv()
TOKEN = os.getenv("INVEST_TOKEN")

if not TOKEN:
    print("ОШИБКА: Токен не найден в .env")
    exit(1)

print("Подключаемся к Т-Инвестициям...")

with Client(TOKEN) as client:
    # Создаём виртуальный счёт
    account = client.sandbox.open_sandbox_account(name="AI Agent Test")
    account_id = account.account_id
    print(f"Счёт создан: {account_id}")
    
    # Пополняем баланс на 1 млн рублей
    client.sandbox.sandbox_pay_in(
        account_id=account_id,
        amount=1000000
    )
    print("Баланс пополнен на 1 000 000 руб.")
    
    # Сохраняем ID счёта в .env
    with open(".env", "a") as f:
        f.write(f"\nACCOUNT_ID={account_id}\n")
    print("ACCOUNT_ID сохранён в .env")