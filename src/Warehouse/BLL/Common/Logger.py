import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Централизованная настройка логирования для всего проекта."""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Шаблон: Время [УРОВЕНЬ] (Имя_Файла:Строка) -> Сообщение
    log_format = "%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) -> %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Базовый конфигуратор для вывода в консоль
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler()
        ]
    )

    # Файловый обработчик с ограничением размера до 5 МБ
    file_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "warehouse.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    file_handler.setLevel(logging.INFO)

    logging.getLogger("").addHandler(file_handler)

    # Показывает сырые SQL-запросы SQLAlchemy прямо в логах для отладки транзакций
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

    logging.info("📝 Логи успешно настроены. История пишется в консоль и файл /logs/warehouse.log")
