import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import RequestException

from exceptions import ParseException, ResponseException

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


logger = logging.getLogger(__name__)
previous_error = ''


def check_tokens():
    """Проверка присутствия переменных окружения."""
    env_variables = {PRACTICUM_TOKEN: 'PRACTICUM_TOKEN',
                     TELEGRAM_TOKEN: 'TELEGRAM_TOKEN',
                     TELEGRAM_CHAT_ID: 'TELEGRAM_CHAT_ID'}
    error_list = []
    for env_var, env_str in env_variables.items():
        if env_var is None:
            logger.critical(f'Нет переменной окружения {env_str}')
            error_list.append(env_var)
            pass
    if not error_list == []:
        return False
    return True


def send_message(bot, message):
    """Отправка уведомления в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        logger.error(f'Не удалось отправить сообщение: {error}')
    else:
        logger.debug(f'Сообщение отправлено: {message}')


def get_api_answer(timestamp):
    """Запрос к API Endpoint."""
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
    except RequestException as error:
        raise ResponseException(error)
    if response.status_code != 200:
        not_200_code = f'Неверный ответ сервера: {response.status_code}'
        raise ResponseException(not_200_code)
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип данных response')
    if 'homeworks' not in response:
        raise KeyError('В ответе API ключ homeworks не найден')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Неверный тип данных homeworks')


def parse_status(homework):
    """Присвоение статуса."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise ParseException('В ответе API ключ homework_name не найден')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ParseException('Неизвестный статус')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Контроллер работы приложения."""
    if not check_tokens():
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_error = ''
    previous_date = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if not response['homeworks']:
                logger.debug('Нет работ на рассмотрении')
                time.sleep(RETRY_PERIOD)
            timestamp = response.get('current_date')
            if str(timestamp) != str(previous_date):
                send_message(bot,
                             parse_status(response.get('homeworks')[0]))
                previous_date = timestamp
                logger.info('Статус изменился')
            previous_error = ''
        except Exception as error:
            message = f'Ошибка: {error}'
            if str(error) != str(previous_error):
                send_message(bot, message)
                previous_error = error
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        filename='homework.log',
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    logging.getLogger('').addHandler(console)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)
    main()
