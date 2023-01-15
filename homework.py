import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import RequestException

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
    format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка присутствия переменных окружения"""
    if (PRACTICUM_TOKEN == None
        or TELEGRAM_TOKEN == None
        or TELEGRAM_CHAT_ID == None):
            logger.critical('Нет переменных окружения')
            return False
    elif (PRACTICUM_TOKEN == ''
        or TELEGRAM_TOKEN == ''
        or TELEGRAM_CHAT_ID == ''):
            logger.critical('Пустое значение переменных окружения')
            return False
    else:
        return True


def send_message(bot, message):
    """Отправка уведомления в Telegram-чат"""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        logger.error(f'Не удалось отправить сообщение: {error}')
    else:
        logger.debug(f'Сообщение отправлено: {message}')


def get_api_answer(timestamp):
    """Запрос к API Endpoint"""
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                         params={
                                             'from_date': timestamp})
    except RequestException as error:
        raise Exception(error)
    if response.status_code != 200:
        error = f'Неверный ответ сервера: {response.status_code}'
        raise Exception(error)
    return response.json()


def check_response(response):
    """Проверка ответа API"""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип данных response')
    elif 'homeworks' not in response:
        raise KeyError('В ответе API ключ homeworks не найден')
    elif not isinstance(response['homeworks'], list):
        raise TypeError('Неверный тип данных homeworks')
    elif len(response['homeworks']) < 1:
        raise Exception('Нет обновлений статуса')


def parse_status(homework):
    """Присвоение статуса"""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise Exception('В ответе API ключ homework_name не найден')
    status = homework.get('status')
    if status not in list(HOMEWORK_VERDICTS.keys()):
        raise Exception('Неизвестный статус')
    verdict = HOMEWORK_VERDICTS[status]
    if HOMEWORK_VERDICTS[status] == '':
        raise Exception('Недокументированный статус')
    else:
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Контроллер работы приложения"""
    if check_tokens() is False:
        raise Exception('Ошибка токенов')
    else:                      
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time())
        while True:
            try:
                new_homework = get_api_answer(timestamp)
                check_response(new_homework)
                send_message(bot, parse_status(new_homework.get('homeworks')[0]))
            except Exception as error:
                message = f'Ошибка: {error}'
                send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
        check_tokens()
        main()
