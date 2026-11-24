# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Endereco do painel.
#   REQUISITOS.......: RF12
#   PROCURE POR......: rota, endereco, painel
# ----------------------------------------------------------------------

from django.urls import path

from . import views

urlpatterns = [
    path('', views.painel, name='painel'),
]
