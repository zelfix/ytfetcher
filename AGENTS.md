# Repository Guidelines

## Project Structure & Module Organization
`main.py` запускает Telegram бота, предварительно загружая переменные из `.env` через `python-dotenv`. Исходники лежат в пакете `ytfetcher/`, где `bot.py` содержит обработчики, выдающие ссылки на файлы, опубликованные nginx из каталога загрузок; названия файлов очищаются и дополнительно маркируются случайным суффиксом. Контейнер генерирует `nginx.conf` при старте (`entrypoint.sh`), поддерживает HTTP/HTTPS и отдачу ACME-челленджей для Let’s Encrypt. `docker-compose.yml` поднимает сервисы `ytfetcher` и `certbot`, заводит именованные тома `downloads`, `certbot-www`, `certbot-etc`. Тесты храните в `tests/`, зеркалируя структуру пакета. При необходимости добавляйте статические шаблоны в `assets/`.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate`: локальное окружение для разработки.
- `pip install -e .[dev]`: ставит пакет, `yt-dlp`, Telegram SDK и dev-инструменты.
- `python main.py`: запускает бота, читая настройки из `.env` или окружения (`TELEGRAM_BOT_TOKEN`, `PUBLIC_BASE_URL`, `DOWNLOAD_ROOT`, `ENABLE_TLS`, `SERVER_NAME`, пути к сертификатам).
- `docker build -t ytfetcher . && docker run -p 8080:8080 …`: самый быстрый способ протестировать связку бота и nginx.

## Coding Style & Naming Conventions
Следуем PEP 8 с 4 пробелами. Публичные функции типизируем, используем `snake_case` для функций/переменных и `PascalCase` для классов. Общие утилиты выносите в независимые модули (`ytfetcher/storage.py`). Форматирование прогоняйте `ruff` и `black` (конфигурацию добавьте в `pyproject.toml`, когда станет актуально).

## Testing Guidelines
Используйте `pytest`. Именуйте файлы `test_<module>.py`, сценарии покрывают обработку ссылок, построение ссылок скачивания и ошибки `yt-dlp`. При тестах сетевые вызовы мокируйте. Для асинхронных функций применяйте `pytest.mark.asyncio`.

## Commit & Pull Request Guidelines
Коммиты в императиве (`Add nginx static hosting`) и небольшими порциями. В PR обязательно описывайте сценарий использования, добавляйте команды валидации (сборка Docker, прогон тестов) и помечайте нужные переменные окружения (`TELEGRAM_BOT_TOKEN`, `PUBLIC_BASE_URL`). Если меняете поведение выдачи ссылок или хранения файлов, приложите заметку о миграции.
