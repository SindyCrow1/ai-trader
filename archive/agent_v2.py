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
# ШАГ 1: Получаем текущую цену SBER
# ============================================================
print("=" * 50)
print("ШАГ 1: Получаем данные о SBER")
print("=" * 50)

with Client(INVEST_TOKEN) as client:
    # Последняя цена
    last_price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
    last_price = last_price_resp.last_prices[0].price
    price_rub = last_price.units + last_price.nano / 1_000_000_000
    print(f"Текущая цена SBER: {last_price.units} руб. {last_price.nano // 10**6} коп.")
    
    # Свечи за последние 2 дня (чтобы понять динамику)
    from datetime import datetime, timedelta
    from t_tech.invest.schemas import CandleInterval
    
    now = datetime.now()
    from_date = now - timedelta(days=2)
    
    candles_resp = client.market_data.get_candles(
        figi=SBER_FIGI,
        from_=from_date,
        to=now,
        interval=CandleInterval.CANDLE_INTERVAL_DAY
    )
    
    if len(candles_resp.candles) >= 2:
        prev_close = candles_resp.candles[-2].close
        prev_price = prev_close.units + prev_close.nano / 1_000_000_000
        change_pct = ((price_rub - prev_price) / prev_price) * 100
        print(f"Изменение за день: {change_pct:+.2f}%")
    else:
        change_pct = 0.0
        print("Недостаточно данных для расчёта изменения")

# ============================================================
# ШАГ 2: Читаем новости из RSS (больше новостей + описания)
# ============================================================
print("\n" + "=" * 50)
print("ШАГ 2: Читаем RSS")
print("=" * 50)

url = "https://rssexport.rbc.ru/rbcnews/news/30/full.rss"
feed = feedparser.parse(url)

# Берём 20 новостей и добавляем описание
news_items = []
for entry in feed.entries[:20]:
    title = entry.title
    # Обрезаем описание до 200 символов
    summary = getattr(entry, 'summary', '')[:200]
    news_items.append(f"- {title}\n  {summary}")

news_text = "\n".join(news_items)
print(f"Получено {len(news_items)} новостей с описаниями")

# ============================================================
# ШАГ 3: Отправляем в GigaChat расширенный контекст
# ============================================================
print("\n" + "=" * 50)
print("ШАГ 3: Анализ через GigaChat")
print("=" * 50)

prompt = f"""
Ты — торговый аналитик. Проанализируй ситуацию по акциям Сбербанка (SBER).

ТЕКУЩАЯ РЫНОЧНАЯ СИТУАЦИЯ:
- Цена SBER: {last_price.units} руб. {last_price.nano // 10**6} коп.
- Изменение за день: {change_pct:+.2f}%

НОВОСТИ:
{news_text}

ЗАДАЧА:
Оцени, как эти новости влияют на Сбербанк. Учти:
1. Есть ли новости, напрямую касающиеся банковского сектора или Сбера?
2. Есть ли макроэкономические события (ставка ЦБ, инфляция, санкции)?
3. Как текущая динамика цены соотносится с новостным фоном?

Ответь СТРОГО в формате JSON, без пояснений:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование на русском (2-3 предложения)"
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
    
    start = answer.find("{")
    end = answer.rfind("}") + 1
    signal = json.loads(answer[start:end])

# ============================================================
# ШАГ 4: Показываем сигнал
# ============================================================
print("=" * 50)
print("ШАГ 4: Сигнал")
print("=" * 50)
print(f"Действие: {signal['action']}")
print(f"Уверенность: {signal['confidence']}")
print(f"Причина: {signal['reason']}")

# ============================================================
# ШАГ 5: Исполняем сделку (только BUY с уверенностью >= 0.7)
# ============================================================
if signal['action'] == 'BUY' and signal['confidence'] >= 0.7:
    print("\n" + "=" * 50)
    print("ШАГ 5: Покупка SBER")
    print("=" * 50)
    
    with Client(INVEST_TOKEN) as client:
        price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
        price = price_resp.last_prices[0].price
        print(f"Цена покупки: {price.units} руб. {price.nano // 10**6} коп.")
        
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