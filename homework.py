import os
import logging
import time
import requests
from http import HTTPStatus
import sys

from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiException

from exceptions import StatusParsingError, HTTPError, RequestError

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

last_error_message = None


def check_tokens():
    """Проверяет наличие всех токенов."""
    required_tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = [
        token for token, value in required_tokens.items() if value is None
    ]
    if missing_tokens:
        logging.critical(
            'Отсутствуют необходимые переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение чат TG."""
    try:
        logging.debug(f'Бот отправил сообщение {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        return True
    except ApiException as error:
        logging.error(f'Ошибка при отправке сообщения в Telegram: {error}')
        return False
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка при запросе к API Telegram: {error}')
        return False


def get_api_answer(timestamp):
    """Отправляет запрос к endpoint."""
    try:
        params = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        raise RequestError(error)

    if response.status_code != HTTPStatus.OK:
        raise HTTPError(response)
    return response.json()


def check_response(response):
    """Получает и проверяет ответ от endpoint."""
    if not response:
        raise ValueError('Полученный ответ пустой.')
    if not isinstance(response, dict):
        raise TypeError('Некорректный тип ответа.')
    if 'homeworks' not in response:
        raise KeyError('Не хватает ключа "homeworks" в ответе.')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Некорректный формат данных "homeworks".')

    return response['homeworks']


def parse_status(homework):
    """Получает статус дз."""
    if ('homework_name' not in homework) or not homework.get('homework_name'):
        raise KeyError('Отстутствует ключ имени домашней работы')

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if 'status' not in homework:
        raise KeyError('Отстутствует ключ статуса домашней работы.')

    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if homework_status not in HOMEWORK_VERDICTS:
        raise StatusParsingError('Такого статуса нет.')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit(1)

    bot = TeleBot(token=TELEGRAM_TOKEN)
    last_message = None
    timestamp = 0

    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homeworks = check_response(api_answer)

            for homework in homeworks:
                message = parse_status(homework)
                if message != last_message:
                    if send_message(bot, message):
                        last_message = message
                        timestamp = api_answer.get('current_date', timestamp)
        except Exception as error:
            last_message = handle_error(error, bot, last_error_message)

        if not homeworks:
            logging.debug('Нет новых статусов.')

        time.sleep(RETRY_PERIOD)


def handle_error(error, bot, last_error_message=None):
    """Обрабатывает ошибки и отправляет сообщения в Telegram."""
    message = f'Сбой в работе программы: {error}'
    if message != last_error_message:
        send_message(bot, message)
        return message
    logging.error(message)
    return last_error_message


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler('main.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    main()
