from django.urls import path
from . import views

urlpatterns = [
    path('relatorios/', views.lista_relatorios, name='lista_relatorios'),
    path('relatorios/novo/', views.cadastrar_relatorio, name='cadastrar_relatorio'),
]