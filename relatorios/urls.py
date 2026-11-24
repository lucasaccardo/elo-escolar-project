# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Enderecos das telas de relatorio.
#   REQUISITOS.......: RF05, RF06, RF11
#   PROCURE POR......: rota, endereco, relatorios, novo, editar,
#                      excluir
# ----------------------------------------------------------------------

from django.urls import path
from . import views

urlpatterns = [
    path('', views.pagina_inicial, name='inicio'),
    path('relatorios/', views.lista_relatorios, name='lista_relatorios'),
    path('relatorios/novo/', views.cadastrar_relatorio,
         name='cadastrar_relatorio'),
    path('relatorios/<int:pk>/editar/', views.editar_relatorio,
         name='editar_relatorio'),
    path('relatorios/<int:pk>/excluir/', views.excluir_relatorio,
         name='excluir_relatorio'),
]
