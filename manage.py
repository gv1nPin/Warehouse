import os
import sys
import shutil  # Добавили для копирования файлов

def main():
    """Глобальная точка входа веб-сервера."""
    
    # 1. Проверяем наличие .env и автоматически копируем из .env.example, если его нет
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, '.env')
    example_path = os.path.join(current_dir, '.env.example')

    if not os.path.exists(env_path) and os.path.exists(example_path):
        shutil.copy(example_path, env_path)
        print("\n[INFO] Файл .env отсутствовал и был автоматически создан из .env.example\n")

    # 2. Настройки Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings') # Указываем на папку config

    # Вычисляем абсолютный путь к папке 'src' относительно manage.py
    src_path = os.path.join(current_dir, 'src')
    
    # Внедряем src в самый НАЧАЛО путей поиска Python (индекс 0).
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()

