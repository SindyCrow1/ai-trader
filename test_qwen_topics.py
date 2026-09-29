import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
API_KEY = os.getenv("PROXYAPI_KEY")
BASE_URL = os.getenv("PROXYAPI_BASE_URL", "https://api.proxyapi.ru/v1")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

topics = [
    "ЦБ РФ повысил ключевую ставку до 20%",
    "Сбербанк объявил рекордную прибыль за квартал",
    "США ввели новые санкции против российских банков",
    "Путин подписал указ о мобилизации",
    "Сбербанк снизил ставки по ипотеке",
]

for topic in topics:
    prompt = f"""Новость: {topic}

Ответь СТРОГО в формате JSON:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование"
}}
"""
    response = client.chat.completions.create(
        model="qwen/qwen3.7-flash",
        messages=[{"role": "user", "content": prompt}]
    )
    answer = response.choices[0].message.content
    print(f"\nНовость: {topic}")
    print(f"Ответ: {answer[:200]}")
    print("-" * 60)