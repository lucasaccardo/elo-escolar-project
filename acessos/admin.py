from django.contrib import admin

from .models import AceiteTermos, SolicitacaoAcesso


@admin.register(SolicitacaoAcesso)
class SolicitacaoAcessoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'aluno', 'status', 'aceite_termos_em',
                    'criado_em', 'analisado_por')
    list_filter = ('status',)
    search_fields = ('usuario__email', 'aluno__rgm')

    # O pedido nasce no cadastro público; ninguém cria um pela mão.
    def has_add_permission(self, request):
        return False

    # A análise só acontece pela tela de pedidos, que faz tudo junto.
    # O aceite dos termos é prova de consentimento: não pode ser alterado.
    readonly_fields = (
        'aceite_termos_em',
        'criado_em',
        'status',
        'analisado_por',
        'analisado_em',
        'justificativa',
    )


@admin.register(AceiteTermos)
class AceiteTermosAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'versao', 'aceito_em')
    list_filter = ('versao',)
    search_fields = ('usuario__username', 'usuario__email')

    # Prova de consentimento: só o próprio usuário cria, ninguém altera.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False