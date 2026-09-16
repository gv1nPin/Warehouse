from pydantic import BaseModel, Field, ConfigDict

class EmployeeRegisterInputDTO(BaseModel):
    """Входной DTO для регистрации нового сотрудника."""
    first_name: str = Field(..., min_length=2, max_length=50, description="Имя сотрудника")
    last_name: str = Field(..., min_length=2, max_length=50, description="Фамилия сотрудника")
    warehouse_id: int = Field(..., gt=0, description="ID склада, к которому привязан сотрудник")
    role_id: int = Field(..., gt=0, description="ID роли в системе (RBAC)")
    login: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$", description="Уникальный логин (только латиница и цифры)")
    password: str = Field(..., min_length=6, description="Пароль в открытом виде (будет захэширован bcrypt)")

class LoginInputDTO(BaseModel):
    """Входной DTO для формы авторизации."""
    login: str = Field(..., description="Логин сотрудника")
    password: str = Field(..., description="Пароль")

# токен для JWT
class TokenOutputDTO(BaseModel):
    """Выходной DTO, возвращающий JWT-токен в браузер."""
    access_token: str
    token_type: str = "bearer"
    expires_at: str

    model_config = ConfigDict(from_attributes=True)
