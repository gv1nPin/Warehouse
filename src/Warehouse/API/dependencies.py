import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dependency_injector.wiring import inject, Provide

from container import Container
from Warehouse.BLL.Services.AuthService.AuthService import AuthService, AuthException

# Стандартный компонент FastAPI, который ищет заголовок "Authorization: Bearer <JWT-TOKEN>"
security_scheme = HTTPBearer()

class PermissionChecker:
    def __init__(self, required_permission: str):
        """Инициализирует проверку конкретного доменного права доступа.

        Args:
            required_permission (str): Системное имя права (например, 'shipment:create', 'shipment:accept')
        """
        self.required_permission = required_permission

    @inject
    def __call__(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
        auth_service: AuthService = Depends(Provide[Container.auth_service])
    ) -> dict:
        """Метод вызывается автоматически фреймворком FastAPI при каждом входящем запросе."""
        token = credentials.credentials
        try:
            # 1. Декодируем и валидируем подпись токена через наш сервис бизнес-логики BLL
            payload = auth_service.decode_token(token)
            
            # 2. Извлекаем массив запеченных в Payload прав сотрудника
            user_permissions = payload.get("permissions", [])
            
            # 3. Делаем строгую проверку роли/права (RBAC контроля доступа)
            if self.required_permission not in user_permissions:
                logging.warning(
                    f"Безопасность: Сотрудник ID {payload.get('sub')} получил ОТКАЗ "
                    f"в доступе к ресурсу. Требовалось право: '{self.required_permission}'"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Недостаточно прав доступа. Требуется разрешение: '{self.required_permission}'"
                )
            
            # 4. Если всё успешно, возвращаем распакованный payload дальше в эндпоинт роутера
            return payload
            # ошибка входа
        except AuthException as e:
            # Перехватываем ошибки истекшего времени жизни или поддельной цифровой подписи токена
            logging.warning(f"Авторизация сорвалась: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )
