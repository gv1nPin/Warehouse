import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Корень проекта: src/warehouse/common/logger.py -> три уровня вверх.
# Папка логов привязана к нему, а не к текущей папке процесса, поэтому
# manage.py, src/main.py и pytest пишут в один и тот же logs/warehouse.log.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def get_log_dir() -> Path:
    """Папка логов: LOG_DIR из .env, иначе <корень проекта>/logs."""
    custom = os.getenv("LOG_DIR", "").strip()
    return Path(custom) if custom else PROJECT_ROOT / "logs"


def setup_logging():
    """Централизованная настройка логирования для всего проекта."""
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "warehouse.log"

    # Время [УРОВЕНЬ] (Имя_Файла:Строка) -> Сообщение
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
    root = logging.getLogger("")
    already_attached = any(
        isinstance(h, RotatingFileHandler) and h.baseFilename == str(log_file.resolve())
        for h in root.handlers
    )
    if already_attached:
        # Повторный вызов (например, ready() и тесты) не должен дублировать строки в файле.
        return

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    file_handler.setLevel(logging.INFO)

    root.addHandler(file_handler)

    # Показывает сырые SQL-запросы SQLAlchemy прямо в логах для отладки транзакций
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

    logging.info(" Логи успешно настроены. История пишется в консоль и файл %s", log_file)
