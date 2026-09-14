# src/Warehouse/BLL/Interfaces/AbstractAuthService.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class AbstractAuthService(ABC):
    @abstractmethod
    def register_employee(self, first_name: str, last_name: str, warehouse_id: int, role_id: int, login: str, plain_password: str) -> int:
        """Регистрирует нового сотрудника со скрытием пароля в хэш."""
        pass

    @abstractmethod
    def authenticate_employee(self, login: str, plain_password: str) -> Dict[str, Any]:
        """Проверяет учетные данные и возвращает сгенерированный JWT-токен."""
        pass

    @abstractmethod
    def decode_token(self, token: str) -> Dict[str, Any]:
        """Проверяет валидность токена и возвращает payload (данные сессии)."""
        pass
