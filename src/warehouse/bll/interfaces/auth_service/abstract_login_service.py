from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from warehouse.common.dto import EmployeeDTO


@dataclass(frozen=True, slots=True)
class TokenDTO:
    """Результат входа."""

    access_token: str
    token_type: str
    expires_at: datetime
    employee: EmployeeDTO


@dataclass(frozen=True, slots=True)
class TokenPayloadDTO:
    """Что лежит внутри токена."""

    employee_id: int
    warehouse_id: int
    role_name: str
    permissions: frozenset[str]
    expires_at: datetime


class AbstractLoginService(ABC):
    """Вход сотрудника на сайт и проверка токена."""

    @abstractmethod
    def login(self, login: str, password: str) -> TokenDTO:
        """Проверяет логин и пароль, выдаёт токен.

        Неверный логин или пароль -> AuthError с одинаковым текстом.
        """

    @abstractmethod
    def decode_token(self, token: str) -> TokenPayloadDTO:
        """Проверяет подпись и срок токена. Не прошёл -> AuthError."""
