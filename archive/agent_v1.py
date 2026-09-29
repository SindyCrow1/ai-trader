import os
import json
import feedparser
from dotenv import load_dotenv
from gigachat import GigaChat
from t_tech.invest import Client, Quotation
from t_tech.invest.schemas import OrderDirection

# Загружаем ключи из .env
load_dotenv()

AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")
INVEST_TOKEN = os.getenv("INVEST_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
SBER_FIGI = "BBG004730N88"

# ============================================================
# ШАГ 1: Читаем новости из RSS
# ============================================================
print("=" * 50)
print("ШАГ 1: Читаем RSS")
print("=" * 50)

url = "https://rssexport.rbc.ru/rbcnews/news/30/full.rss"
feed = feedparser.parse(url)
news_text = "\n".join([f"- {entry.title}" for entry in feed.entries[:10]])
print(f"Получено {len(feed.entries[:10])} новостей:")
for entry in feed.entries[:10]:
    print(f"  • {entry.title}")

# ============================================================
# ШАГ 2: Отправляем новости в GigaChat на анализ
# ============================================================
print("\n" + "=" * 50)
print("ШАГ 2: Анализ через GigaChat")
print("=" * 50)

prompt = f"""
Ты — торговый аналитик. Проанализируй новости и дай рекомендацию по акциям Сбербанка (SBER).

Новости:
{news_text}

Ответь СТРОГО в формате JSON, без пояснений:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование на русском"
}}
"""

with GigaChat(
    credentials=AUTH_KEY,
    verify_ssl_certs=False,
    model="GigaChat-3-Ultra"
) as giga:
    response = giga.chat(prompt)
    answer = response.choices[0].message.content
    print(f"Ответ модели:\n{answer}\n")
    
    # Извлекаем JSON из ответа
    start = answer.find("{")
    end = answer.rfind("}") + 1
    signal = json.loads(answer[start:end])

# ============================================================
# ШАГ 3: Показываем сигнал
# ============================================================
print("=" * 50)
print("ШАГ 3: Сигнал")
print("=" * 50)
print(f"Действие: {signal['action']}")
print(f"Уверенность: {signal['confidence']}")
print(f"Причина: {signal['reason']}")

# ============================================================
# ШАГ 4: Исполняем сделку (только BUY с уверенностью >= 0.7)
# ============================================================
if signal['action'] == 'BUY' and signal['confidence'] >= 0.7:
    print("\n" + "=" * 50)
    print("ШАГ 4: Покупка SBER")
    print("=" * 50)
    
    with Client(INVEST_TOKEN) as client:
        # Получаем текущую цену SBER
        price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
        price = price_resp.last_prices[0].price
        print(f"Текущая цена SBER: {price.units} руб. {price.nano // 10**6} коп.")
        
        # Покупаем 1 акцию
        order = client.sandbox.post_sandbox_order(
            account_id=ACCOUNT_ID,
            figi=SBER_FIGI,
            quantity=1,
            price=Quotation(units=price.units, nano=price.nano),
            direction=OrderDirection.ORDER_DIRECTION_BUY,
            order_type=1
        )
        print(f"Заявка отправлена: {order.order_id}")
        print(f"Статус: {order.execution_report_status}")
else:
    print(f"\nСигнал {signal['action']} — сделка не выполняется")
    if signal['action'] == 'BUY':
        print(f"(уверенность {signal['confidence']} ниже порога 0.7)")