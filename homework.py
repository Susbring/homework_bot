import os
import logging
import requests
import time

from dotenv import load_dotenv
from telebot import TeleBot
from http import HTTPStatus

from exceptions import StError, HTTPError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='main.log',
    encoding='utf-8'
)


def check_tokens():
    """Проверяет наличие всех токенов."""
    required_tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    missing_tokens = [token for token in required_tokens if token is None]
    if missing_tokens:
        message = "Отсутствуют необходимые переменные окружения"
        logging.critical(message)
        raise EnvironmentError(message)
    return True


def send_message(bot, message):
    """Отправляет сообщение чат TG."""
    try:
        logging.debug(f'Бот отправил сообщение {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(error)


def get_api_answer(timestamp):
    """Отправляет запрос к endpoint."""
    try:
        params = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise HTTPError(response)
        return response.json()
    except requests.RequestException as error:
        logging.error(f'Ошибка при запросе к API: {error}')
        return None
    except ValueError as error:
        logging.error(f'Ошибка при парсинге JSON: {error}')


def check_response(response):
    """Получает и проверяет ответ от endpoint."""
    if not response:
        message = 'Полученный ответ пустой.'
        logging.error(message)
        raise KeyError(message)
    if not isinstance(response, dict):
        message = 'Некорректный тип.'
        logging.error(message)
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'Не хватает ключа в ответе.'
        logging.error(message)
        raise KeyError(message)
    if not isinstance(response.get('homeworks'), list):
        message = 'Некорректный формат ответа.'
        logging.error(message)
        raise TypeError(message)

    return response['homeworks']


def parse_status(homework):
    """Получает статус дз."""
    if 'homework_name' not in homework:
        message = 'Отстутствует ключ имени домашней работы'
        logging.warning(message)
        raise KeyError(message)

    if not homework.get('homework_name'):
        homework_name = 'None'
        logging.warning('Имя домашней работы отсутствует!')
    else:
        homework_name = homework.get('homework_name')

    homework_status = homework.get('status')
    if 'status' not in homework:
        message = 'Отстутствует ключ статуса домашней работы.'
        logging.error(message)
        raise KeyError(message)

    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Такого статуса нет.'
        logging.error(message)
        raise StError(message)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    last_message = {}
    timestamp = int(time.time())

    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homeworks = check_response(api_answer)

            if not homeworks:
                logging.debug('Нет новых статусов.')
                time.sleep(RETRY_PERIOD)
                continue

            process_homeworks(homeworks, bot, last_message)
            timestamp = api_answer.get('current_date', timestamp)

        except Exception as error:
            handle_error(error, bot)

        time.sleep(RETRY_PERIOD)


def process_homeworks(homeworks, bot, last_message):
    """Обрабатывает список домашних работ и отправляет сообщения о статусах."""
    for homework in homeworks:
        try:
            message = parse_status(homework)
            if last_message.get(homework['homework_name']) != message:
                send_message(bot, message)
                last_message[homework['homework_name']] = message
        except Exception as error:
            logging.error(error)


def handle_error(error, bot):
    """Обрабатывает ошибки и отправляет сообщения в Telegram."""
    message = f'Сбой в работе программы: {error}'
    send_message(bot, message)
    logging.exception(message)


if __name__ == '__main__':
    main()
