import os
import sys

def main():
    """Глобальная точка входа веб-сервера."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings') # Указываем на папку config

    # Вычисляем абсолютный путь к папке 'src' относительно аmanage.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(current_dir, 'src')
    
    # Внедряем src в самый НАЧАЛО путей поиска Python (индекс 0).
    # Теперь и Django, и авторелоадер, и Pylance всегда будут видеть 'container' и 'warehouse'
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
