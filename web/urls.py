from django.urls import path

from . import views

app_name = 'first'

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.products, name='products'),
    path('products/new/', views.product_new, name='product_new'),
    path('counter/', views.counter, name='counter'),
]
