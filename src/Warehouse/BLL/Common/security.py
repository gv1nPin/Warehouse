# src/Warehouse/BLL/Common/security.py
import bcrypt

def hash_password(password: str) -> str:
    """Генерирует безопасный хэш пароля с солью bcrypt."""
    # Переводим строку в байты
    pwd_bytes = password.encode('utf-8')
    # Генерируем соль и хэш
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    # Возвращаем хэш в виде обычной строки для сохранения в текстовое поле таблицы Employees
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет соответствие открытого пароля сохраненному хэшу."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )
