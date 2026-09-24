from django.apps import AppConfig
import sys
import os

class WebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'web' 

    def ready(self) -> None:
        import logging
        
        # Вычисляем и добавляем путь к src, чтобы подстраховать авторелоадер
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src_path = os.path.join(base_dir, 'src')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
            
        from container import Container
        from warehouse.common.logger import setup_logging
        
        setup_logging()
        container = Container()
        
        # ФИКС: Проклеиваем зависимости в реальный файл представлений 'web.views'
        container.wire(modules=["web.views"])
        
        logging.info("DI-Контейнер и SQLAlchemy успешно запущены в слое web.")
