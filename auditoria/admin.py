from django.contrib import admin

from .models import Evento


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = (
        'quando',
        'acao',
        'usuario',
        'usuario_informado',
        'detalhe',
    )
    list_filter = ('acao',)
    search_fields = ('usuario__username', 'usuario_informado', 'detalhe')

    # Log não se escreve à mão, não se edita e não se apaga.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False