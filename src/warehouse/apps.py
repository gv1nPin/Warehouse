from django.apps import AppConfig
import sys
import os

class WarehouseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'src.warehouse' if 'src.warehouse' in sys.modules or True else 'warehouse' 

    def ready(self) -> None:
        import logging
        
        # ГАРАНТИЯ ИМПОРТА: Принудительно добавляем корень 'src' в пути поиска текущего потока Django
        # Это гарантирует, что 'container' и 'warehouse' будут видны из любой точки проекта
        src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
            
        # Теперь импорты отработают без ошибок на любой операционной системе
        from container import Container
        from warehouse.common.logger import setup_logging
        
        setup_logging()
        
        container = Container()
        
        # указываем имя модуля контроллеров так же, как оно импортируется Django
        container.wire(modules=["warehouse.views"])
        
        logging.info(" DI-Контейнер и SQLAlchemy успешно запущены в Django.")
