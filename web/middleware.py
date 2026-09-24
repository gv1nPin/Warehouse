from django.http import JsonResponse
from warehouse.common.exceptions import BusinessError
from warehouse.dal.database import scoped_session_factory

class SQLAlchemyAndBusinessErrorMiddleware:
    """Управляет транзакциями SQLAlchemy и маппит бизнес-ошибки в Django."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Используем try-finally, чтобы remove() вызвался ВСЕГДА,
        # даже если контроллер упал с системной ошибкой (500)
        try:
            response = self.get_response(request)
            return response
        finally:
            scoped_session_factory.remove()

    def process_exception(self, request, exception):
        # ФИКС ПОВТОРНОЙ ОЧИСТКИ: На случай, если исключение вылетело до get_response 
        # или в других middleware, подчищаем сессию и здесь
        scoped_session_factory.remove()
        
        # Превращаем доменные исключения (400, 403, 409) в красивые JSON-ответы
        if isinstance(exception, BusinessError):
            return JsonResponse(
                {"error": exception.message},
                status=exception.status_code
            )
        # Системные ошибки (500) пробрасываем дальше в Django
        return None
