from dependency_injector.wiring import Provide, inject
from container import Container
from Warehouse.BLL.Services.AuthService import AuthService

@inject
def main(auth_service: AuthService = Provide[Container.auth_service]):
    # Контейнер сам подставит сюда auth_service благодаря декоратору @inject
    print(" Проект запущен, Dependency Injection работает через declarative container.")
    print(f" Сервис авторизации успешно извлечен: {auth_service}")

if __name__ == "__main__":
    # Инициализируем контейнер и запускаем wiring для main
    container = Container()
    main()
