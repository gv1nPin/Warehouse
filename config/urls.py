"""
URL configuration for server project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from web.views import (
    PrototypeCabinetView, 
    CreateDraftView, 
    LoginView, 
    StockListView,
    ShipStageView,
    AcceptStageView
)

urlpatterns = [
    # Главная страница кабинета
    path('', PrototypeCabinetView.as_view(), name='cabinet'),
    
    # API Авторизации
    path('api/auth/login/', LoginView.as_view(), name='login'),
    
    # API Складских остатков
    path('api/stock/', StockListView.as_view(), name='stock_list'),
    
    # API Управления перевозками (Черновик, Отгрузка, Приёмка)
    path('api/shipments/draft/', CreateDraftView.as_view(), name='create_draft'),
    path('api/stages/<int:stage_id>/ship/', ShipStageView.as_view(), name='ship_stage'),
    path('api/stages/<int:stage_id>/accept/', AcceptStageView.as_view(), name='accept_stage'),
]
