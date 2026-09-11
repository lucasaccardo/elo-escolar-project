from django.urls import path
from . import views

urlpatterns = [
    path('relatorios/', views.lista_relatorios, name='lista_relatorios'),
]