# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Enderecos das telas de cadastro, confirmacao e
#                      aprovacao.
#   REQUISITOS.......: RF02, RF03, RF14
#   PROCURE POR......: rota, endereco, cadastro, confirmar, pedidos
# ----------------------------------------------------------------------

from django.urls import path

from . import views

urlpatterns = [
    path('cadastro/', views.cadastro_responsavel, name='cadastro'),
    path('cadastro/confirmar/', views.confirmar_email,
         name='confirmar_email'),
    path('cadastro/confirmar/reenviar/', views.reenviar_codigo,
         name='reenviar_codigo'),
    path('cadastro/enviado/', views.cadastro_enviado, name='cadastro_enviado'),
    path('termos/', views.termos_de_uso, name='termos'),
    path('termos/aceitar/', views.aceitar_termos, name='aceitar_termos'),
    path('privacidade/', views.politica_privacidade, name='privacidade'),
    path('pedidos/', views.fila_aprovacao, name='fila_aprovacao'),
    path('pedidos/<int:pk>/aprovar/', views.aprovar_solicitacao,
         name='aprovar_solicitacao'),
    path('pedidos/<int:pk>/recusar/', views.recusar_solicitacao,
         name='recusar_solicitacao'),
]
