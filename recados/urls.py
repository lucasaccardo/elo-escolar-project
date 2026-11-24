# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Enderecos das telas de recado.
#   REQUISITOS.......: RF09
#   PROCURE POR......: rota, endereco, recados, novo
# ----------------------------------------------------------------------

from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista_recados, name='lista_recados'),
    path('novo/', views.cadastrar_recado, name='cadastrar_recado'),
]
