import os
from dotenv import load_dotenv
from t_tech.invest import Client, Quotation
from t_tech.invest.schemas import OrderDirection

load_dotenv()
TOKEN = os.getenv("INVEST_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

GAZP_FIGI = "BBG004730RP0"

with Client(TOKEN) as client:
    # Получаем цену GAZP
    price_resp = client.market_data.get_last_prices(figi=[GAZP_FIGI])
    price = price_resp.last_prices[0].price
    print(f"Цена GAZP: {price.units} руб. {price.nano // 10**6} коп.")
    
    # Пробуем купить 1 акцию
    try:
        order = client.sandbox.post_sandbox_order(
            account_id=ACCOUNT_ID,
            figi=GAZP_FIGI,
            quantity=1,
            price=Quotation(units=price.units, nano=price.nano),
            direction=OrderDirection.ORDER_DIRECTION_BUY,
            order_type=1
        )
        print(f"Заявка отправлена: {order.order_id}")
        print(f"Статус: {order.execution_report_status}")
    except Exception as e:
        print(f"Ошибка: {e}")