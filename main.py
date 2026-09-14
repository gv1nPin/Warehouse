from src.Warehouse.DAL.Session import session_factory
from src.Warehouse.DAL.SQLAlchemyUnitOfWork import SQLAlchemyUnitOfWork
# Предположим, у вас есть сервис в слое BLL
# from src.Warehouse_BLL.Services.DispatchService import DispatchService 

def main():
    # 1. Инициализируем Unit of Work, передавая ему фабрику сессий
    uow = SQLAlchemyUnitOfWork(session_factory=session_factory)
    
    # 2. Внедряем зависимость UOW в слой бизнес-логики (Dependency Injection)
    # dispatch_service = DispatchService(uow=uow)
    
    # Пример того, как сервис будет использовать эту сборку внутри себя:
    print("Приложение успешно инициализировано с SQLAlchemy UOW!")
    
    # Демонстрация работы контекста:
    # with uow:
    #     # Доступны все репозитории с автодополнением типов в IDE
    #     stage = uow.transit.get_stage_by_id(stage_id=1)
    #     if stage:
    #         uow.dispatch.update_stage_status(stage_id=1, status_id=2)
    #     # Здесь UOW автоматически вызовет session.commit() при выходе из блока

if __name__ == "__main__":
    main()
