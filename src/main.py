from dependency_injector.wiring import Provide, inject
from container import Container
from Warehouse.BLL.Services.AuthService.AuthService import AuthService
from Warehouse.BLL.Common.Logger import setup_logging

@inject
def main(auth_service: AuthService = Provide[Container.auth_service]):
    # Теперь контейнер автоматически подставит сюда НАСТОЯЩИЙ объект класса
    print(" Проект запущен, Dependency Injection работает через declarative container.")
    
    # Это докажет, что внедрился живой объект, а не заглушка Provide
    print(f" Сервис авторизации успешно извлечен: {auth_service}")
    print(f" Доступные методы сервиса: {dir(auth_service)}")

if __name__ == "__main__":
    # 1. Инициализируем логи СРАЗУ ЖЕ при старте программы
    setup_logging()

    # 2. Создаем экземпляр контейнера
    container = Container()
       
    # связываем контейнер с текущим файлом main.py
    # Это заставит декоратор @inject корректно подставлять зависимости
    container.wire(modules=[__name__])
    
    # 3. Запускаем приложение
    main()
