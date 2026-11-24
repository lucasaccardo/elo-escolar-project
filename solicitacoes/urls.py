# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Enderecos das telas de solicitacao.
#   REQUISITOS.......: RF10
#   PROCURE POR......: rota, endereco, solicitacoes
# ----------------------------------------------------------------------

from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista_solicitacoes, name='lista_solicitacoes'),
    path('nova/', views.abrir_solicitacao, name='abrir_solicitacao'),
    path('<int:pk>/responder/', views.responder_solicitacao,
         name='responder_solicitacao'),
    path('<int:pk>/encerrar/', views.encerrar_solicitacao,
         name='encerrar_solicitacao'),
]
