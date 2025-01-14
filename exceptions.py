class HTTPError(Exception):
    """Проверка доступности endpoint."""

    def __init__(self, response):
        message = (
            f'Endpoint {response.url} недоступен. '
            f'Код ответа API: {response.status_code}'
        )
        super().__init__(message)


class StatusParsingError(Exception):
    """Проверка ошибки статуса."""

    def __init__(self, text):
        message = (
            f'Парсинг ответа API: {text}'
        )
        super().__init__(message)


class RequestError(Exception):
    """Ошибка при запросе к API"""

    def __init__(self, text):
        message = (
            f'Ошибка при запросе к API: {text}'
        )
        super().__init__(message)
