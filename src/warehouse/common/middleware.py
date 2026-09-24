from django.http import JsonResponse
from warehouse.common.exceptions import BusinessError
from warehouse.dal.database import scoped_session_factory

class SQLAlchemyAndBusinessErrorMiddleware:
    """Управляет транзакциями SQLAlchemy и маппит бизнес-ошибки в Django."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # После отправки ответа клиенту обязательно зачищаем сессию потока
        scoped_session_factory.remove()
        return response

    def process_exception(self, request, exception):
        # Гарантируем закрытие сессии при падении
        scoped_session_factory.remove()
        
        # Фикс: превращаем ваши доменные исключения (400, 403, 409) в красивые JSON-ответы
        if isinstance(exception, BusinessError):
            return JsonResponse(
                {"error": exception.message},
                status=exception.status_code
            )
        return None
