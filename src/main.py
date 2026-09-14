from Warehouse.DAL.Database import session_factory
from Warehouse.container import Container

def main():
    # Инициализируем контейнер для проверки
    container = Container()
    print("Проект запущен, пути импорта настроены абсолютно верно.")
    print(f"Фабрика сессий успешно загружена: {session_factory}")

if __name__ == "__main__":
    main()
