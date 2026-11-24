# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Como os recados aparecem no painel
#                      administrativo.
#   REQUISITOS.......: RF09
#   PROCURE POR......: admin, list_display
# ----------------------------------------------------------------------

from django.contrib import admin

from .models import Recado


@admin.register(Recado)
class RecadoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'turma', 'exibir_ate', 'autor', 'publicado_em')
    list_filter = ('turma', 'exibir_ate')
    search_fields = ('titulo', 'mensagem')
    date_hierarchy = 'publicado_em'
