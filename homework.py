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
    hmwrks_is_not_list,
    error_api_request,
    endpoint_is_not_available,
    error_api_to_json,
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

# Время, через которое будет срабатывать бот (в секундах).
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

# Список выбрасываемых ошибок.
error_messages = []


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
            f"отправлено в чат {TELEGRAM_CHAT_ID}"
        )
        return True
    except ApiTelegramException as error:
        logger.error(f"Ошибка при отправке сообщения: {error}")
        return False


def get_api_answer(timestamp):
    """Функция-обработчик эндпоинта."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={"from_date": timestamp}
        )
        response.raise_for_status()
    except requests.RequestException as e:
        error_message = f"{error_api_request} {e}"
        logger.error(error_message)
        error_messages.append(error_message)
        raise ApiErrorException(error_message)

    if response.status_code != HTTPStatus.OK:
        error_message = f"{endpoint_is_not_available}{response.status_code}"
        logger.error(error_message)
        error_messages.append(error_message)
        raise NotAvailableEndPointException(error_message)

    try:
        return response.json()
    except ValueError as e:
        error_message = f"{error_api_to_json}{e}"
        logger.error(error_message)
        error_messages.append(error_message)
        raise ApiErrorException(error_message)


def check_response(response):
    """Функция валидации ответа из функции get_api_answer."""
    if not isinstance(response, dict):
        error_message = api_is_not_dict
        logger.error(error_message)
        error_messages.append(error_message)
        raise TypeError(error_message)
    if "homeworks" not in response or "current_date" not in response:
        error_message = empty_api_keys
        logger.error(error_message)
        error_messages.append(error_message)
        raise KeyError(error_message)
    if not isinstance(response["homeworks"], list):
        error_message = hmwrks_is_not_list
        logger.error(error_message)
        error_messages.append(error_message)
        raise TypeError(error_message)
    return response


def parse_status(homework):
    """Функция обновления статуса работы."""
    if "homework_name" not in homework or "status" not in homework:
        error_message = empty_hmwrks_keys
        logger.error(error_message)
        error_messages.append(error_message)
        raise KeyError(error_message)
    homework_name = homework["homework_name"]
    status = homework["status"]
    if status not in HOMEWORK_VERDICTS:
        error_message = f"{not_doc_status} {status}"
        logger.error(error_message)
        error_messages.append(error_message)
        raise ValueError(error_message)
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    last_error_message = None
    last_error_time = 0
    RETRY_PERIOD_ERROR_TIME = 5000  # В секундах.

    while True:
        try:
            response = get_api_answer(timestamp)
            logger.debug(f"Ответ от API: {response}")
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
            error_messages.append(message)

            current_time = time.time()
            if (
                message != last_error_message
                or current_time - last_error_time > RETRY_PERIOD_ERROR_TIME
            ):
                if send_message(bot, message):
                    last_error_message = message
                    last_error_time = current_time
                else:
                    logger.debug(
                        "Анти-спам обнаружение. Сообщение не отправлено."
                    )
        finally:
            try:
                for error_message in error_messages:
                    if send_message(bot, error_message):
                        error_messages.remove(error_message)

            except Exception as e:
                logger.critical(
                    "Невозможно отправить сообщение об ошибке"
                    f" пользователю: {e}."
                )

            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
