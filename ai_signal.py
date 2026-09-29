import os
import json
from dotenv import load_dotenv
from gigachat import GigaChat

load_dotenv()

AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")

# Тестовая новость — потом заменим на реальный источник
news = """
ЦБ РФ неожиданно повысил ключевую ставку на 2 п.п. до 16% годовых. 
Аналитики ожидали сохранения ставки. Рынок акций отреагировал падением, 
банковский сектор под давлением.
"""

prompt = f"""
Ты — торговый аналитик. Проанализируй новость и дай рекомендацию 
по акциям Сбербанка (SBER).

Новость: {news}

Ответь СТРОГО в формате JSON, без пояснений:
{{
  "action": "BUY" | "SELL" | "HOLD",
  "ticker": "SBER",
  "confidence": 0.0-1.0,
  "reason": "краткое обоснование на русском"
}}
"""

print("Отправляем новость в GigaChat...")

with GigaChat(
    credentials=AUTH_KEY,
    verify_ssl_certs=False,
    model="GigaChat-3-Ultra"
) as giga:
    response = giga.chat(prompt)
    answer = response.choices[0].message.content
    print(f"\nОтвет модели:\n{answer}")
    
    # Пробуем распарсить JSON
    try:
        # Ищем JSON в ответе (модель иногда добавляет текст вокруг)
        start = answer.find("{")
        end = answer.rfind("}") + 1
        signal = json.loads(answer[start:end])
        print(f"\n✅ Распарсенный сигнал:")
        print(f"   Действие: {signal['action']}")
        print(f"   Тикер: {signal['ticker']}")
        print(f"   Уверенность: {signal['confidence']}")
        print(f"   Причина: {signal['reason']}")
    except Exception as e:
        print(f"\n❌ Не удалось распарсить JSON: {e}")