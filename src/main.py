from contextlib import asynccontextmanager
from fastapi import FastAPI
from dependency_injector.wiring import Provide, inject

from container import Container
from warehouse.bll.services.auth_service.auth_service import AuthService
from warehouse.common.logger import setup_logging

# Импортируем готовые роутеры для Web-слоя
from warehouse.api.auth import router as Auth_router
from warehouse.api.shipments import router as Shipments_router


# НОВЫЙ СИНТАКСИС: Управляет жизненным циклом приложения FastAPI
@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # Данный блок выполняется СТРОГО ОДИН РАЗ при старте веб-сервера uvicorn
    setup_logging()
    yield
    # Данный блок выполнится при штатной остановке сервера (если нужно закрыть коннекты)
    pass


@inject
def test_console_run(auth_service: AuthService = Provide[Container.auth_service]):
    """Тестовая функция для верификации графа зависимостей IoC в консоли."""
    print(" Проект запущен, Dependency Injection работает через declarative container.")
    print(f" Сервис авторизации успешно извлечен: {auth_service}")
    print(f" Доступные методы сервиса: {dir(auth_service)}")


def create_app() -> FastAPI:
    """Фабрика веб-приложения для сервера uvicorn."""
    
    # 1. Инициализируем IoC контейнер
    container = Container()
    
    # 2. Связываем контейнер со всеми модулями
    container.wire(modules=[
        __name__,
        "warehouse.api.auth",
        "warehouse.api.shipments",
        "warehouse.api.mappers.auth_mappers",
        "warehouse.api.mappers.shipments_mappers"
    ])
    
    # 3. Инициализируем фреймворк FastAPI и передаем ему наш lifespan-менеджер
    fastapi_app = FastAPI(
        title="WMS Warehouse API",
        description="Система сквозного весового контроля и учета перемещения грузов",
        version="1.0.0",
        lifespan=lifespan  # 🔥 Передаем lifespan вместо on_event
    )
    
    # 4. Регистрируем эндпоинты в веб-сервере
    fastapi_app.include_router(Auth_router)
    fastapi_app.include_router(Shipments_router)
    
    # Сохраняем ссылку на собранный контейнер внутри приложения
    fastapi_app.container = container
    
    return fastapi_app


# Создаем глобальный объект для uvicorn (веб-запуск)
app = create_app()

# Блок ручного запуска из консоли (команда: python main.py)
if __name__ == "__main__":
    setup_logging()  # Инициализация логов один раз только при ручном старте CLI
    print("Вызов приложения из CLI консоли...")
    test_console_run()
