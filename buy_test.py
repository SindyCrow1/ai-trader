import os
from dotenv import load_dotenv
from t_tech.invest import Client, Quotation
from t_tech.invest.schemas import OrderDirection

load_dotenv()
TOKEN = os.getenv("INVEST_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

with Client(TOKEN) as client:
    # Ищем акцию Сбербанка по тикеру
    instruments = client.instruments.find_instrument(query="SBER")
    
    sber = None
    for inst in instruments.instruments:
        if inst.ticker == "SBER" and inst.class_code == "TQBR":
            sber = inst
            break
    
    if not sber:
        print("Не нашли SBER")
        exit(1)
    
    print(f"Нашли: {sber.name} ({sber.ticker})")
    print(f"FIGI: {sber.figi}")
    
    # Покупаем 1 акцию по рыночной цене
    response = client.sandbox.post_sandbox_order(
        account_id=ACCOUNT_ID,
        figi=sber.figi,
        quantity=1,
        price=Quotation(units=272, nano=6000000),
        direction=OrderDirection.ORDER_DIRECTION_BUY,
        order_type=1
    )
    
    print(f"Заявка отправлена: {response.order_id}")
    print(f"Статус: {response.execution_report_status}")