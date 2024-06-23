import os
import logging
from logging import StreamHandler
from http import HTTPStatus
import time
import sys

import requests
from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiTelegramException

from exceptions import ApiErrorException, NotAvailableEndPointException
from constants import (
    api_is_not_dict,
    empty_api_keys,
    empty_hmwrks_keys,
    not_doc_status,
    hmwrks_is_not_list
)

load_dotenv()

# Токены для работы.
PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Словарь для работы с токенами.
TOKENS = {
    "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
    "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
    "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
}


# Время, через которое будет срабатывать бот ( в секундах ).
RETRY_PERIOD = 600

# ENDPOINT
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"

# Заголовки.
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

# Вердикты.
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
            logger.critical(
                f'Отсутствует обязательная переменная окружения: "{name}".\n'
                "Программа принудительно остановлена."
            )
            sys.exit(1)
    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
        or TELEGRAM_TOKEN is None
    ):
        logger.critical(
            f'Отсутствует обязательная переменная окружения: "{name}".\n'
            "Программа принудительно остановлена."
        )
        sys.exit(1)
    return True


def send_message(bot, message):
    """Функция, отправляет пользователю сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(
            f'Сообщение "{message}" успешно '
            f'отправлено в чат {TELEGRAM_CHAT_ID}'
        )
    except ApiTelegramException as error:
        logger.error(f"Ошибка при отправке сообщения: {error}")


def get_api_answer(timestamp):
    """Функция-обработчик эндпоинта."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={"from_date": timestamp}
        )
    except requests.RequestException:
        logger.error("Ошибка при запросе к API.")

    except ApiTelegramException as error:
        logger.error(f"Ошибка {error} при запросе к API.")
        raise ApiErrorException(f"Ошибка {error} при запросе к API.")

    if response.status_code != HTTPStatus.OK:
        logger.error(
            f"Эндпоинт {ENDPOINT} недоступен. "
            f"Код ответа API: {response.status_code}"
        )
        raise NotAvailableEndPointException(
            f"Эндпоинт {ENDPOINT} недоступен. "
            f"Код ответа API: {response.status_code}"
        )
    return response.json()


def check_response(response):
    """Функция валидации ответа из функции get_api_answer."""
    if not isinstance(response, dict):
        logger.error(api_is_not_dict)
        raise TypeError(api_is_not_dict)
    if "homeworks" not in response or "current_date" not in response:
        logger.error(empty_api_keys)
        raise KeyError(empty_api_keys)
    if not isinstance(response["homeworks"], list):
        logger.error(hmwrks_is_not_list)
        raise TypeError(hmwrks_is_not_list)
    return response


def parse_status(homework):
    """Функция обновления статуса работы."""
    if "homework_name" not in homework or "status" not in homework:
        logger.error(
            empty_hmwrks_keys
        )
        raise KeyError(
            empty_hmwrks_keys
        )
    homework_name = homework["homework_name"]
    status = homework["status"]
    if status not in HOMEWORK_VERDICTS:
        logger.error(
            f"{not_doc_status} {status}"
        )
        raise ValueError(
            f"{not_doc_status} {status}"
        )
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens() and check_tokens is None:
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
                logger.debug("Новых статусов нет.")

            timestamp = response["current_date"]

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
