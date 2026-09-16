from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmployeeDTO:
    id: int
    first_name: str
    last_name: str
    login: str
    role_id: int
    role_name: str
    warehouse_id: int
    is_deleted: bool

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name}"


@dataclass(frozen=True, slots=True)
class EmployeeAuthDTO:
    """Только для входа на сайт: сотрудник + хэш пароля."""

    employee: EmployeeDTO
    password_hash: str
