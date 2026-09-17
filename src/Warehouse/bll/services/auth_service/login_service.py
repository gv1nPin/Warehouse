import secrets
from datetime import datetime, timedelta, timezone

import jwt

from Warehouse.bll.exceptions import AuthError
from Warehouse.bll.interfaces.auth_service import (
    AbstractAccessService,
    AbstractLoginService,
    TokenDTO,
    TokenPayloadDTO,
)
from Warehouse.common.security import verify_password
from Warehouse.dal.unit_of_work import UnitOfWork

ALGORITHM = "HS256"
INVALID_CREDENTIALS = "Неверный логин или пароль"

# Если ключ не передан, используется этот: он создаётся один раз при запуске приложения
# и общий для всех экземпляров сервиса. После перезапуска старые токены перестают
# работать — сотрудникам нужно войти заново.
_GENERATED_SECRET = secrets.token_urlsafe(64)


class LoginService(AbstractLoginService):
    """Вход сотрудника на сайт и проверка токена (JWT)."""

    def __init__(
        self,
        uow: UnitOfWork,
        access: AbstractAccessService,
        secret_key: str | None = None,
        expire_minutes: int = 8 * 60,
    ) -> None:
        self.uow = uow
        self.access = access
        self._secret_key = secret_key or _GENERATED_SECRET
        self._expire = timedelta(minutes=expire_minutes)

    def login(self, login: str, password: str) -> TokenDTO:
        login = (login or "").strip()
        if not login or not password:
            raise AuthError(INVALID_CREDENTIALS)

        with self.uow as uow:
            auth = uow.employees.get_auth_by_login(login)
            # Одинаковый текст для «нет логина» и «неверный пароль»,
            # чтобы нельзя было подобрать существующие логины.
            if auth is None or not self._password_matches(password, auth.password_hash):
                raise AuthError(INVALID_CREDENTIALS)
            actor = self.access.get_actor(uow, auth.employee.id)

        now = datetime.now(timezone.utc)
        expires_at = now + self._expire
        payload = {
            "sub": str(actor.employee.id),
            "warehouse_id": actor.employee.warehouse_id,
            "role_name": actor.employee.role_name,
            "permissions": sorted(actor.permissions),
            "iat": now,
            "exp": expires_at,
        }
        token = jwt.encode(payload, self._secret_key, algorithm=ALGORITHM)
        return TokenDTO(
            access_token=token,
            token_type="bearer",
            expires_at=expires_at,
            employee=actor.employee,
        )

    def decode_token(self, token: str) -> TokenPayloadDTO:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[ALGORITHM],
                options={"require": ["sub", "exp"]},
            )
            return TokenPayloadDTO(
                employee_id=int(payload["sub"]),
                warehouse_id=payload["warehouse_id"],
                role_name=payload["role_name"],
                permissions=frozenset(payload["permissions"]),
                expires_at=datetime.fromtimestamp(payload["exp"], timezone.utc),
            )
        except jwt.ExpiredSignatureError:
            raise AuthError("Сессия истекла, войдите заново") from None
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            raise AuthError("Недействительный токен, войдите заново") from None

    @staticmethod
    def _password_matches(password: str, password_hash: str) -> bool:
        try:
            return verify_password(password, password_hash)
        except ValueError:
            # Битый хэш в БД считаем неверным паролем.
            return False
