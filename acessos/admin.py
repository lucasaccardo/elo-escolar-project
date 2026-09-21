from django.contrib import admin

from .models import SolicitacaoAcesso


@admin.register(SolicitacaoAcesso)
class SolicitacaoAcessoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'aluno', 'status', 'criado_em', 'analisado_por')
    list_filter = ('status',)
    search_fields = ('usuario__email', 'aluno__rgm')

    # A análise só acontece pela tela de pedidos, que faz tudo junto.
    readonly_fields = (
        'criado_em',
        'status',
        'analisado_por',
        'analisado_em',
        'justificativa',
    )