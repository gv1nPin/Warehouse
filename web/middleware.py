from django.http import JsonResponse

from warehouse.common.exceptions import BusinessError
from warehouse.dal.database import scoped_session_factory


class SQLAlchemyAndBusinessErrorMiddleware:
    """Закрывает сессию SQLAlchemy после запроса и отдаёт бизнес-ошибки API в JSON."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        finally:
            scoped_session_factory.remove()

    def process_exception(self, request, exception):
        scoped_session_factory.remove()
        if isinstance(exception, BusinessError) and request.path.startswith('/api/'):
            return JsonResponse({"error": exception.message}, status=exception.status_code)
        return None
