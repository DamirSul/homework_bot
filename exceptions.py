class ApiErrorException(Exception):
    "Ошибка при запросе к API"
    pass


class NotAvailableEndPointException(Exception):
    "Недоступность эндпоинта"
    pass
