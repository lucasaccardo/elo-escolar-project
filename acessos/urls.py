from django.urls import path

from . import views

urlpatterns = [
    path('cadastro/', views.cadastro_responsavel, name='cadastro'),
    path('cadastro/enviado/', views.cadastro_enviado, name='cadastro_enviado'),
    path('termos/', views.termos_de_uso, name='termos'),
    path('privacidade/', views.politica_privacidade, name='privacidade'),
]
