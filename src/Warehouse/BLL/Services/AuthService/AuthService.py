import jwt
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from Warehouse.BLL.Interfaces.AuthService.AbstractAuthService import AbstractAuthService
from Warehouse.BLL.Common.security import hash_password, verify_password

class AuthException(Exception): pass
class InvalidCredentialsException(AuthException): pass
class TokenExpiredException(AuthException): pass
class InvalidTokenException(AuthException): pass

class AuthService(AbstractAuthService):
    def __init__(self, uow):
        self.uow = uow
        # В реальном проекте берите эти значения из переменных окружения (.env)
        self.secret_key = os.getenv("JWT_SECRET_KEY", "SUPER_SECRET_SKLAD_KEY_9999")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60 * 8  # Токен активен рабочую смену (8 часов)

    def register_employee(self, first_name: str, last_name: str, warehouse_id: int, role_id: int, login: str, plain_password: str) -> int:
        with self.uow:
            # 1. Проверяем, не занят ли логин
            existing_user = self.uow.employee.get_by_login(login)
            if existing_user:
                raise AuthException("Сотрудник с таким логином уже зарегистрирован.")

            # 2. Превращаем открытый пароль в безопасный необратимый хэш
            pwd_hash = hash_password(plain_password)

            # 3. Создаем объект модели через сессию SQLAlchemy
            from src.Warehouse.DAL.Entities.Warehouses import Employee
            new_employee = Employee(
                first_name=first_name,
                last_name=last_name,
                warehouse_id=warehouse_id,
                role_id=role_id,
                login=login,
                password_hash=pwd_hash
            )
            self.uow.session.add(new_employee)
            self.uow.session.flush()  # Запрашиваем сгенерированный ID
            return new_employee.id

    def authenticate_employee(self, login: str, plain_password: str) -> Dict[str, Any]:
        with self.uow:
            # 1. Ищем сотрудника в БД по логину
            employee_orm = self.uow.employee.get_by_login(login)
            if not employee_orm:
                raise InvalidCredentialsException("Неверный логин или пароль.")

            # 2. Проверяем валидность пароля через bcrypt
            if not verify_password(plain_password, employee_orm.password_hash):
                raise InvalidCredentialsException("Неверный login или пароль.")

            # 3. Вытаскиваем список его атомарных прав для запекания в JWT
            employee_data = self.uow.employee.get_by_id_with_permissions(employee_orm.id)
            permissions = employee_data.get("permissions", []) if employee_data else []

            # 4. Формируем Payload токена
            now = datetime.now(timezone.utc)
            expire = now + timedelta(minutes=self.access_token_expire_minutes)
            
            payload = {
                "sub": str(employee_orm.id),                     # Идентификатор субъекта
                "warehouse_id": employee_orm.warehouse_id,        # К какому складу привязан
                "permissions": permissions,                      # Список прав (RBAC)
                "iat": now,                                      # Время создания
                "exp": expire                                    # Время протухания
            }

            # 5. Кодируем токен
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            return {
                "access_token": token,
                "token_type": "bearer",
                "expires_at": expire.isoformat()
            }

    def decode_token(self, token: str) -> Dict[str, Any]:
        """Декодирует и верифицирует JWT. Используется в API Middleware/Dependencies."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise TokenExpiredException("Срок действия токена авторизации истек.")
        except jwt.PyJWTError:
            raise InvalidTokenException("Предоставлен некорректный токен доступа.")
