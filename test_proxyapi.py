import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("PROXYAPI_KEY")
BASE_URL = os.getenv("PROXYAPI_BASE_URL", "https://api.proxyapi.ru/v1")

if not API_KEY:
    print("ОШИБКА: PROXYAPI_KEY не найден в .env")
    exit(1)

print("Подключаемся к ProxyAPI...")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

try:
    response = client.chat.completions.create(
        model="qwen/qwen3.7-flash",
        messages=[{"role": "user", "content": "Привет! Ответь одним предложением на русском."}]
    )
    print(f"Ответ модели: {response.choices[0].message.content}")
except Exception as e:
    print(f"ОШИБКА: {e}")