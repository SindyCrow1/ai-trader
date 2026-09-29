import os
import json
import feedparser
from dotenv import load_dotenv
from gigachat import GigaChat
from t_tech.invest import Client, Quotation
from t_tech.invest.schemas import OrderDirection, CandleInterval
from datetime import datetime, timedelta

load_dotenv()

AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")
INVEST_TOKEN = os.getenv("INVEST_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
SBER_FIGI = "BBG004730N88"

# Ключевые слова для фильтрации (только значимые для Сбера)
KEYWORDS = [
    "сбер", "сбербанк", "банк", "банковск", "цб", "центробанк", 
    "ставк", "ключев", "акци", "бирж", "санкц", "рубл", "инфляц", 
    "кредит", "ипотек", "вклад", "финанс", "мобилизац", "балтик"
]

# ============================================================
# ШАГ 1: Получаем данные о SBER
# ============================================================
print("=" * 50)
print("ШАГ 1: Данные о SBER")
print("=" * 50)

with Client(INVEST_TOKEN) as client:
    last_price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
    last_price = last_price_resp.last_prices[0].price
    price_rub = last_price.units + last_price.nano / 1_000_000_000
    print(f"Цена SBER: {last_price.units} руб. {last_price.nano // 10**6} коп.")
    
    now = datetime.now()
    from_date = now - timedelta(days=2)
    candles_resp = client.market_data.get_candles(
        figi=SBER_FIGI, from_=from_date, to=now,
        interval=CandleInterval.CANDLE_INTERVAL_DAY
    )
    
    if len(candles_resp.candles) >= 2:
        prev_close = candles_resp.candles[-2].close
        prev_price = prev_close.units + prev_close.nano / 1_000_000_000
        change_pct = ((price_rub - prev_price) / prev_price) * 100
        print(f"Изменение за день: {change_pct:+.2f}%")
    else:
        change_pct = 0.0

# ============================================================
# ШАГ 2: Читаем RSS и ФИЛЬТРУЕМ новости
# ============================================================
print("\n" + "=" * 50)
print("ШАГ 2: Читаем RSS и фильтруем")
print("=" * 50)

url = "https://rssexport.rbc.ru/rbcnews/news/30/full.rss"
feed = feedparser.parse(url)

all_news = feed.entries[:30]
filtered_news = []

for entry in all_news:
    title_lower = entry.title.lower()
    summary = getattr(entry, 'summary', '')[:200]
    text_lower = (title_lower + " " + summary.lower())
    
    # Проверяем, есть ли хоть одно ключевое слово
    if any(kw in text_lower for kw in KEYWORDS):
        filtered_news.append(f"- {entry.title}\n  {summary}")

print(f"Всего новостей: {len(all_news)}")
print(f"После фильтрации: {len(filtered_news)}")
for n in filtered_news:
    print(f"  {n.split(chr(10))[0]}")

# ============================================================
# ШАГ 3: Анализ через GigaChat
# ============================================================
print("\n" + "=" * 50)
print("ШАГ 3: Анализ через GigaChat")
print("=" * 50)

if not filtered_news:
    print("Нет релевантных новостей — сигнал HOLD")
    signal = {"action": "HOLD", "confidence": 0.5, "reason": "Нет новостей, релевантных Сберу"}
else:
    news_text = "\n".join(filtered_news)
    prompt = f"""
Ты — торговый аналитик. Проанализируй ситуацию по акциям Сбербанка (SBER).

ТЕКУЩАЯ РЫНОЧНАЯ СИТУАЦИЯ:
- Цена SBER: {last_price.units} руб. {last_price.nano // 10**6} коп.
- Изменение за день: {change_pct:+.2f}%

РЕЛЕВАНТНЫЕ НОВОСТИ (отфильтрованы по ключевым словам):
{news_text}

ЗАДАЧА:
Оцени влияние этих новостей на Сбербанк и дай рекомендацию.

Ответь СТРОГО в формате JSON:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование на русском (2-3 предложения)"
}}
"""
    
    with GigaChat(
        credentials=AUTH_KEY, verify_ssl_certs=False, model="GigaChat-3-Ultra"
    ) as giga:
        response = giga.chat(prompt)
        answer = response.choices[0].message.content
        print(f"Ответ модели:\n{answer}\n")
        start = answer.find("{")
        end = answer.rfind("}") + 1
        signal = json.loads(answer[start:end])

# ============================================================
# ШАГ 4: Сигнал
# ============================================================
print("=" * 50)
print("ШАГ 4: Сигнал")
print("=" * 50)
print(f"Действие: {signal['action']}")
print(f"Уверенность: {signal['confidence']}")
print(f"Причина: {signal['reason']}")

# ============================================================
# ШАГ 5: Сделка
# ============================================================
if signal['action'] == 'BUY' and signal['confidence'] >= 0.7:
    print("\nШАГ 5: Покупка SBER")
    with Client(INVEST_TOKEN) as client:
        price_resp = client.market_data.get_last_prices(figi=[SBER_FIGI])
        price = price_resp.last_prices[0].price
        order = client.sandbox.post_sandbox_order(
            account_id=ACCOUNT_ID, figi=SBER_FIGI, quantity=1,
            price=Quotation(units=price.units, nano=price.nano),
            direction=OrderDirection.ORDER_DIRECTION_BUY, order_type=1
        )
        print(f"Заявка: {order.order_id}, статус: {order.execution_report_status}")
else:
    print(f"\nСигнал {signal['action']} — сделка не выполняется")