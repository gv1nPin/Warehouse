class BusinessError(Exception):
    """Базовый класс для всех бизнес-ошибок сервиса."""
    status_code: int = 500

    def __init__(self, message: str = "Произошла внутренняя ошибка бизнес-логики"):
        self.message = message
        super().__init__(self.message)


class ValidationError(BusinessError):
    """Неверные данные в запросе (например, не пройдена валидация полей)."""
    status_code: int = 400

    def __init__(self, message: str = "Переданы неверные данные"):
            super().__init__(message)


class AuthError(BusinessError):
    """Ошибка аутентификации (неверный логин, пароль или токен)."""
    status_code: int = 401

    def __init__(self, message: str = "Неверный логин, пароль или токен"):
            super().__init__(message)


class AccessDeniedError(BusinessError):
    """Ошибка авторизации (нет прав доступа или попытка обратиться к чужому складу)."""
    status_code: int = 403

    def __init__(self, message: str = "Доступ запрещен или у вас нет прав на этот склад"):
            super().__init__(message)


class NotFoundError(BusinessError):
    """Запрашиваемая запись не найдена в базе данных или была удалена."""
    status_code: int = 404

    def __init__(self, message: str = "Запись не найдена или удалена"):
            super().__init__(message)


class InvalidStatusError(BusinessError):
    """Действие запрещено для текущего статуса сущности."""
    status_code: int = 409  

    def __init__(self, message: str = "Запрошенное действие запрещено в текущем статусе"):
            super().__init__(message)
                                