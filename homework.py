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
    error_api_to_json
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
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"{error_api_request} {e}")
        send_message(TELEGRAM_CHAT_ID, f"{error_api_request} {e}")
        raise ApiErrorException(f"{error_api_request} {e}")

    if response.status_code != HTTPStatus.OK:
        logger.error(
            f"{endpoint_is_not_available}{response.status_code}"
        )
        send_message(TELEGRAM_CHAT_ID, f"{endpoint_is_not_available}{response.status_code}")
        raise NotAvailableEndPointException(
           f"{endpoint_is_not_available}{response.status_code}"
        )

    try:
        return response.json()
    except ValueError as e:
        logger.error(f"{error_api_to_json}{e}")
        send_message(
            TELEGRAM_CHAT_ID,
            f"{error_api_to_json}{e}"
        )
        raise ApiErrorException(f"{error_api_to_json}{e}")


def check_response(response):
    """Функция валидации ответа из функции get_api_answer."""
    if not isinstance(response, dict):
        send_message(TELEGRAM_CHAT_ID, text=api_is_not_dict) 
        logging.error(api_is_not_dict)
        raise TypeError(api_is_not_dict) 
    if "homeworks" not in response or "current_date" not in response:
        send_message(TELEGRAM_CHAT_ID, text=empty_api_keys)
        logging.error(empty_api_keys) 
        raise KeyError(empty_api_keys) 
    if not isinstance(response["homeworks"], list):
        send_message(TELEGRAM_CHAT_ID, text=hmwrks_is_not_list)
        logging.error(hmwrks_is_not_list) 
        raise TypeError(hmwrks_is_not_list) 
    return response


def parse_status(homework):
    """Функция обновления статуса работы."""
    if "homework_name" not in homework or "status" not in homework:
        logger.error(empty_hmwrks_keys)
        send_message(TELEGRAM_CHAT_ID, empty_hmwrks_keys)
        raise KeyError(empty_hmwrks_keys)
    homework_name = homework["homework_name"]
    status = homework["status"]
    if status not in HOMEWORK_VERDICTS:
        logger.error(f"{not_doc_status} {status}")
        send_message(TELEGRAM_CHAT_ID, f"{not_doc_status} {status}")
        raise ValueError(f"{not_doc_status} {status}")
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
    RETRY_PERIOD_ERROR_TIME = 5000 # В секундах.

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
            
            current_time = time.time()
            if message != last_error_message or current_time - last_error_time > RETRY_PERIOD_ERROR_TIME:
                send_message(bot, message)
                last_error_message = message
                last_error_time = current_time
            else:
                logger.debug("Повторяющееся сообщение об ошибке не отправлено для предотвращения спама.")
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
