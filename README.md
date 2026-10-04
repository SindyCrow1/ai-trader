# AI Trading Agent

Торговый агент для Московской биржи на базе LLM (Qwen) и T-Invest API.
Работает в песочнице Т-Инвестиций, торгует акцией SBER.

## Что делает

1. Получает цену SBER через T-Invest API
2. Читает новости из 3 источников (РБК, Интерфакс, Коммерсантъ)
3. Фильтрует новости по ключевым словам
4. Считает технические индикаторы: RSI(14), MA20, MA50, объём
5. Отправляет всё в Qwen (через ProxyAPI) для анализа
6. Получает сигнал: BUY / SELL / HOLD + confidence
7. Проверяет риск-менеджмент (лимит позиции, лимит сделок, стоп-лосс)
8. Совершает сделку через T-Invest API
9. Логирует всё в agent_log.txt и trades_log.txt

## Архитектура

Цена SBER → RSS новости → Фильтр → Тех.анализ → Qwen → Сигнал → Риск-менеджмент → Сделка → Лог


## Технологии

- Python 3.13.1
- T-Invest API (`t-tech-investments` 1.51.0)
- Qwen через ProxyAPI (OpenAI-совместимый API)
- feedparser, schedule, python-dotenv

## Риск-менеджмент

- **MAX_POSITION = 5** — не более 5 акций SBER
- **MAX_TRADES_PER_DAY = 2** — не более 2 сделок в день
- **STOP_LOSS_PERCENT = 5.0** — стоп-лосс 5%
- **TRADE_START_HOUR = 9 / TRADE_END_HOUR = 23** — только в часы торгов

## Что уже сделано

- ✅ Счёт в песочнице (1 млн руб.)
- ✅ 4 автоматические сделки (покупки SBER)
- ✅ Риск-менеджмент работает (лимит 5/5)
- ✅ Qwen даёт осмысленные сигналы (BUY с confidence 0.65–0.75)
- ✅ Логирование
- ✅ Мульти-акционный агент v9 (SBER + GAZP)

## Что в планах

- ⏳ Увеличить лимиты (20 + 20 акций)
- ⏳ Добавить третью акцию (LKOH или ROSN)
- ⏳ ML-модель (CatBoost) для прогноза цен
- ⏳ VPS для работы 24/7
- ⏳ Переход на реальный счёт (после стабильной прибыли)

## Как запустить

1. Установить зависимости:

py -m pip install t-tech-investments python-dotenv openai feedparser schedule


2. Создать `.env` с ключами:
INVEST_TOKEN=...
TINKOFF_SANDBOX=true
ACCOUNT_ID=...
PROXYAPI_KEY=...
PROXYAPI_BASE_URL=https://api.proxyapi.ru/v1

3. Запустить:
py agent_loop.py

## История проекта

Подробная история, ошибки и решения — в файле `PROGRESS.md`.