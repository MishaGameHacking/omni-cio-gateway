# Бесплатный приватный шлюз Omni-CIO → T-Invest

## Что делает
GPT обращается к вашему HTTPS-адресу Render.
Render хранит секрет T-Invest в переменной окружения.
Python SDK T-Invest подключается с SSL_TBANK_VERIFY=True и использует встроенный сертификат внутри библиотеки.

На телефон и компьютер сертификат не устанавливается.

## Файлы
- main.py — шлюз;
- requirements.txt — зависимости;
- render.yaml — настройки Render;
- 01_FULL_GPT_INSTRUCTIONS_GATEWAY_COMPACT.txt — полный текст для замены Instructions;
- 02_GATEWAY_DATA_CONTRACT_KNOWLEDGE.txt — справка для Knowledge.

## Секреты
Никогда не записывать токены в GitHub.

Render Environment:
TINVEST_TOKEN = новый read-only токен одного счёта.
GATEWAY_API_KEY = отдельный длинный случайный пароль.
SSL_TBANK_VERIFY = True.

## Этапы
1. Создать приватный GitHub-репозиторий.
2. Загрузить main.py, requirements.txt, render.yaml и .gitignore.
3. Render → New → Blueprint или Web Service → подключить репозиторий.
4. Выбрать Free.
5. В Environment добавить два секрета.
6. Дождаться Deploy live.
7. Открыть https://ВАШ-СЕРВИС.onrender.com/health.
8. В GPT удалить прямой T-Invest Action.
9. Создать Action:
   Authentication → API Key → Bearer → GATEWAY_API_KEY.
10. Import from URL:
    https://ВАШ-СЕРВИС.onrender.com/openapi.json
11. Добавить текст файла 01 в Instructions.
12. Загрузить файл 02 в Knowledge.
13. Test: вызвать getConnection, затем getPortfolioSnapshot.

## Бесплатный Render
Free-сервис засыпает после 15 минут без входящих запросов.
Первый запуск после сна может занимать около минуты.
Перед использованием GPT откройте /health и дождитесь status=ok.
Локальная файловая система временная, но шлюзу хранение файлов не нужно.


Полный Instructions содержит 6083 символов и помещается в лимит 8000.
