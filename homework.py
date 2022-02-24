import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_TIME = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_STATUSES = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}
logging.basicConfig(
    level=logging.DEBUG,
    filename="program.log",
    filemode="w",
    format="%(asctime)s, %(levelname)s, %(message)s, %(name)s",
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение о новом статусе домашней работы в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info(f"Успешная отправка сообщения: {message}")
    except Exception as error:
        logger.error(f"Сбой при отправке сообщения в Telegram: {error}")


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API сервиса Практикум.Домашка."""
    timestamp = current_timestamp or int(time.time())
    params = {"from_date": timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != HTTPStatus.OK:
        logger.error(f"Эндпоинт {ENDPOINT} недоступен")
        raise exceptions.APIAnswerIsNot200Error("API недоступен")
    return response.json()


def check_response(response):
    """Проверяет ответ API сервиса Практикум.Домашка на корректность."""
    if response["homeworks"] == []:
        return {}
    if isinstance(response["homeworks"], list):
        return response["homeworks"]
    logger.error("В ответе пришёл неизвестный класс")
    raise exceptions.UnexpectedClassError("Неизвестный класс")


def parse_status(homework):
    """Извлекает статус из информации о конкретной домашней работе."""
    try:
        homework_name = homework.get("homework_name")
        homework_status = homework.get("status")
    except Exception as error:
        message = f"{error}: в ответе отсутствует ожидаемый ключ"
        logger.error(message)
        raise KeyError("Неизвестный ключ")
    if homework_status not in HOMEWORK_STATUSES:
        message = "В ответе пришёл неизвестный статус домашней работы"
        logger.error(message)
        raise KeyError("Неизвестный статус")
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if PRACTICUM_TOKEN is None:
        logger.critical(
            "Отсутствует обязательная переменная окружения PRACTICUM_TOKEN"
        )
        return False
    if TELEGRAM_TOKEN is None:
        logger.critical(
            "Отсутствует обязательная переменная окружения TELEGRAM_TOKENN"
        )
        return False
    if TELEGRAM_CHAT_ID is None:
        logger.critical(
            "Отсутствует обязательная переменная окружения TELEGRAM_CHAT_ID"
        )
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    first_status = "reviewing"
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework and first_status != homework[0]["status"]:
                message = parse_status(homework[0])
                send_message(bot, message)
            current_timestamp = response.get("current_date")
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            logger.error(message)
            time.sleep(RETRY_TIME)


if __name__ == "__main__":
    main()
