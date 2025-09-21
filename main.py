import logging
import os

from dotenv import load_dotenv

load_dotenv()

from ytfetcher import build_application


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Переменная окружения TELEGRAM_BOT_TOKEN не задана.")

    base_url = os.getenv("PUBLIC_BASE_URL")
    if not base_url:
        raise SystemExit("Задайте PUBLIC_BASE_URL, чтобы формировать ссылки на скачивание через nginx.")

    application = build_application(token)
    logging.info("Стартуем бота. Файлы будут доступны по базовому URL %s", base_url)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
