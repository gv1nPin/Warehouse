class BusinessLogicException(Exception):
    """Базовое исключение для всей бизнес-логики (BLL).
    
    Все специфичные ошибки сервисов должны наследоваться от него.
    """
    pass


class InsufficientStockException(BusinessLogicException):
    """Исключение, возникающее при недостатке товара на складе."""
    pass


class EntityNotFoundException(BusinessLogicException):
    """Исключение, возникающее, если сущность (например, Shipment, Employee) не найдена."""
    pass


class AccessDeniedException(BusinessLogicException):
    """Исключение для ситуаций, когда у сотрудника нет прав на операцию."""
    pass
