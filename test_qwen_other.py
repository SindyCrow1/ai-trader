import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
API_KEY = os.getenv("PROXYAPI_KEY")
BASE_URL = os.getenv("PROXYAPI_BASE_URL", "https://api.proxyapi.ru/v1")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

stocks = [
    ("GAZP", "Газпром", "BBG004730RP0"),
    ("LKOH", "Лукойл", "BBG004731032"),
    ("ROSN", "Роснефть", "BBG004731354"),
    ("GMKN", "Норникель", "BBG004731489"),
]

for ticker, name, figi in stocks:
    prompt = f"""Проанализируй акции {name} ({ticker}).
Ответь СТРОГО в формате JSON:
{{
  "action": "BUY" или "SELL" или "HOLD",
  "confidence": число от 0.0 до 1.0,
  "reason": "краткое обоснование на русском"
}}"""
    
    response = client.chat.completions.create(
        model="qwen/qwen3.7-flash",
        messages=[{"role": "user", "content": prompt}]
    )
    answer = response.choices[0].message.content
    print(f"\n{ticker} ({name}):")
    print(answer[:300])
    print("-" * 60)