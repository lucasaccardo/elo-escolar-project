# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Como as solicitacoes aparecem no painel
#                      administrativo.
#   REQUISITOS.......: RF10
#   PROCURE POR......: admin, list_display, situacao
# ----------------------------------------------------------------------

from django.contrib import admin

from .models import Solicitacao


@admin.register(Solicitacao)
class SolicitacaoAdmin(admin.ModelAdmin):
    list_display = ('assunto', 'aluno', 'tipo', 'situacao', 'autor',
                    'aberta_em')
    list_filter = ('situacao', 'tipo')
    search_fields = ('assunto', 'descricao')
    date_hierarchy = 'aberta_em'
    # A situação e a resposta só mudam pelas telas próprias, que carimbam
    # autor e data e registram no log. Trocar o campo aqui deixaria o
    # sistema se contradizendo, como já acontecia com o pedido de acesso.
    readonly_fields = ('situacao', 'resposta', 'respondida_por',
                       'respondida_em', 'encerrada_em', 'aberta_em')
