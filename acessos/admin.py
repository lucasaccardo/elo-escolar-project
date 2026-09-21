from django.contrib import admin

from .models import SolicitacaoAcesso


@admin.register(SolicitacaoAcesso)
class SolicitacaoAcessoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'aluno', 'status', 'criado_em', 'analisado_por')
    list_filter = ('status',)
    search_fields = ('usuario__email', 'aluno__rgm')
    readonly_fields = ('criado_em',)