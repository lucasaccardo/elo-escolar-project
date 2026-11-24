# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Endereco da tela do log de auditoria.
#   REQUISITOS.......: RF07
#   PROCURE POR......: rota, endereco, auditoria, log
# ----------------------------------------------------------------------

from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista_eventos, name='log_auditoria'),
]
