from django.contrib import messages
from django.shortcuts import render

from ..errors import redirect_back


def stub_page(request, title: str):
    """Страница-заглушка «в разработке»."""
    return render(request, 'web/stub.html', {'title': title})


def stub_action(request, title: str):
    """Кнопка-заглушка: сообщает «в разработке» и возвращает назад."""
    messages.info(request, f'{title}: в разработке')
    return redirect_back(request)
