import os
import logging
import time
import requests
from http import HTTPStatus
import sys

from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiException

from exceptions import StatusParsingError, HTTPError

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
        sys.exit(1)
    return True


def send_message(bot, message):
    """Отправляет сообщение чат TG."""
    try:
        logging.debug(f'Бот отправил сообщение {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except ApiException as error:
        logging.error(f'Ошибка при отправке сообщения в Telegram: {error}')
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка при запросе к API Telegram: {error}')
    except Exception as error:
        logging.error(f'Неизвестная ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Отправляет запрос к endpoint."""
    try:
        params = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException:
        return
    except ValueError:
        return

    if response.status_code != HTTPStatus.OK:
        raise HTTPError(response)
    return response.json()


def check_response(response):
    """Получает и проверяет ответ от endpoint."""
    if not response:
        message = 'Полученный ответ пустой.'
        raise KeyError(message)
    if not isinstance(response, dict):
        message = 'Некорректный тип.'
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'Не хватает ключа в ответе.'
        raise KeyError(message)
    if not isinstance(response.get('homeworks'), list):
        message = 'Некорректный формат ответа.'
        raise TypeError(message)

    return response['homeworks']


def parse_status(homework):
    """Получает статус дз."""
    if ('homework_name' not in homework) or not homework.get('homework_name'):
        message = 'Отстутствует ключ имени домашней работы'
        logging.warning(message)
        raise KeyError(message)

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
        raise StatusParsingError(message)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    last_message = None
    timestamp = int(time.time())

    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homeworks = check_response(api_answer)

            for homework in homeworks:
                try:
                    message = parse_status(homework)
                    if message != last_message:
                        send_message(bot, message)
                        last_message = message
                except Exception as error:
                    logging.error(error)
            timestamp = api_answer.get('current_date', timestamp)
        except Exception as error:
            handle_error(error, bot)

        if not homeworks:
            logging.debug('Нет новых статусов.')

        time.sleep(RETRY_PERIOD)


def handle_error(error, bot):
    """Обрабатывает ошибки и отправляет сообщения в Telegram."""
    global last_error_message
    message = f'Сбой в работе программы: {error}'
    if message != last_error_message:
        last_error_message = message
        send_message(bot, message)
    logging.error(message)


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
