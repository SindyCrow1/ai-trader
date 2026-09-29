import os
from dotenv import load_dotenv
from gigachat import GigaChat

load_dotenv()

AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")

if not AUTH_KEY:
    print("ОШИБКА: GIGACHAT_AUTH_KEY не найден в .env")
    exit(1)

print("Подключаемся к GigaChat...")

# Здесь добавили параметр model
with GigaChat(
    credentials=AUTH_KEY, 
    verify_ssl_certs=False, 
    model="GigaChat-3-Ultra"
) as giga:
    response = giga.chat("Привет! Ты работаешь? Ответь одним предложением.")
    print(f"Ответ модели: {response.choices[0].message.content}")