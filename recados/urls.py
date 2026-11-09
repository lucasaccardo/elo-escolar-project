from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista_recados, name='lista_recados'),
    path('novo/', views.cadastrar_recado, name='cadastrar_recado'),
]
