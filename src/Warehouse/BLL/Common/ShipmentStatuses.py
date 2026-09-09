from enum import IntEnum

class ShipmentStatus(IntEnum):
    DRAFT = 1          # Черновик
    SHIPPED = 2        # Отправлено
    RECEIVED = 3       # Принято без расхождений
    RESERVED = 4       # Зарезервировано
    IN_WAITING = 5     # В ожидании (для будущих этапов транзита)
    DISCREPANCY = 6    # Принято с расхождениями
    IN_TRANSIT_WH = 7  # На транзитном складе
