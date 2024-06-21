import os
import logging
from logging import StreamHandler
from http import HTTPStatus
import time
import sys

import requests
from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TOKENS = {
    "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
    "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
    "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
}

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

# Настройки логгирования.
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
handler.setFormatter(formatter)


def check_tokens():
    """Функция проверки токенов."""
    for name, value in TOKENS.items():
        if not value:
            logging.critical(
                f'Отсутствует обязательная переменная окружения: "{name}".\n'
                "Программа принудительно остановлена."
            )
            sys.exit(1)
    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
        or TELEGRAM_TOKEN is None
    ):
        logging.critical(
            f'Отсутствует обязательная переменная окружения: "{name}".\n'
            "Программа принудительно остановлена."
        )
        sys.exit(1)
    return True


def send_message(bot, message):
    """Функция, отправляет пользователю сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(
            f'Сообщение "{message}" успешно '
            f'отправлено в чат {TELEGRAM_CHAT_ID}'
        )
    except Exception as error:
        logging.error(f"Ошибка при отправке сообщения: {error}")
        send_message(
            bot, message=f"Ошибка при отправке сообщения: {error}"
        )


def get_api_answer(timestamp):
    """Функция-обработчик эндпоинта."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={"from_date": timestamp}
        )
        if response.status_code != HTTPStatus.OK:
            logging.error(
                f"Эндпоинт {ENDPOINT} недоступен. "
                f"Код ответа API: {response.status_code}"
            )
            raise Exception(
                f"Эндпоинт {ENDPOINT} недоступен. "
                f"Код ответа API: {response.status_code}"
            )
        return response.json()
    
    except requests.RequestException:
        logging.error(f"Ошибка при запросе к API.")

    except Exception as error:
        logging.error(f"Ошибка {error} при запросе к API.")
        raise



def check_response(response):
    """Функция валидации ответа из функции get_api_answer."""
    if not isinstance(response, dict):
        logging.error("Ответ API не является словарём")
        raise TypeError("Ответ API не является словарём")
    if "homeworks" not in response or "current_date" not in response:
        logging.error("Отсутствуют ожидаемые ключи в ответе API")
        raise KeyError("Отсутствуют ожидаемые ключи в ответе API")
    if not isinstance(response["homeworks"], list):
        logging.error('Поле "homeworks" не является списком')
        raise TypeError('Поле "homeworks" не является списком')
    return response


def parse_status(homework):
    """Функция обновления статуса работы."""
    if "homework_name" not in homework or "status" not in homework:
        logging.error(
            "Отсутствуют ожидаемые ключи в ответе о домашней работе"
        )
        raise KeyError(
            "Отсутствуют ожидаемые ключи в ответе о домашней работе"
        )
    homework_name = homework["homework_name"]
    status = homework["status"]
    if status not in HOMEWORK_VERDICTS:
        logging.error(
            f"Недокументированный статус домашней работы: {status}"
        )
        raise ValueError(
            f"Недокументированный статус домашней работы: {status}"
        )
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens() and check_tokens() is None:
        return

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:

        try:
            response = get_api_answer(timestamp)
            response = check_response(response)

            if response["homeworks"]:
                for homework in response["homeworks"]:
                    message = parse_status(homework)
                    send_message(bot, message)
            else:
                logging.debug("Новых статусов нет.")

            timestamp = response["current_date"]

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)




if __name__ == "__main__":
    main()
