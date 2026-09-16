from fastapi import FastAPI
from dependency_injector.wiring import Provide, inject

from container import Container
from Warehouse.BLL.Services.AuthService.AuthService import AuthService
from Warehouse.BLL.Common.Logger import setup_logging

# Импортируем готовые роутеры для Web-слоя
from Warehouse.API.Auth import router as auth_router
from Warehouse.API.Shipments import router as shipments_router

@inject
def test_console_run(auth_service: AuthService = Provide[Container.auth_service]):
    """Тестовая функция для верификации графа зависимостей IoC в консоли."""
    print(" Проект запущен, Dependency Injection работает через declarative container.")
    print(f" Сервис авторизации успешно извлечен: {auth_service}")
    print(f" Доступные методы сервиса: {dir(auth_service)}")


def create_app() -> FastAPI:
    """Фабрика веб-приложения для сервера uvicorn.""" #этого нет пока
    # 1. Настраиваем систему логирования
    setup_logging()

    # 2. Создаем экземпляр IoC контейнера
    container = Container()
    
    # 3. КРИТИЧЕСКИ ВАЖНО: Связываем контейнер со всеми файлами, 
    # где используется декоратор @inject (включая этот файл и слой API роутеров)
    container.wire(modules=[
        __name__,
        "Warehouse.API.auth",
        "Warehouse.API.Shipments"
    ])
    
    # 4. Инициализируем фреймворк FastAPI
    fastapi_app = FastAPI(
        title="WMS Warehouse API",
        description="Система сквозного весового контроля и учета перемещения грузов",
        version="1.0.0"
    )
    
    # 5. Регистрируем эндпоинты в веб-сервере
    fastapi_app.include_router(auth_router)
    fastapi_app.include_router(shipments_router)
    
    # Сохраняем ссылку на собранный контейнер внутри приложения
    fastapi_app.container = container
    
    return fastapi_app


# Создаем глобальный объект для uvicorn (веб-запуск)
app = create_app()

# Блок ручного запуска из консоли (команда: python main.py)
if __name__ == "__main__":
    print("Вызов приложения из CLI консоли...")
    # Так как при прямом вызове python main.py фабрика create_app уже отработала 
    # в глобальной области видимости, контейнер уже создал wire-связи с __name__.
    # Мы можем сразу безопасно вызвать тестовый метод.
    test_console_run()
