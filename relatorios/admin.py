from django.contrib import admin
from .models import Turma, RelatorioDiario, Aluno, Perfil

@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ano_letivo', 'professor')

@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'rgm', 'turma')
    list_filter = ('turma',)
    search_fields = ('nome_completo', 'rgm')

@admin.register(RelatorioDiario)
class RelatorioDiarioAdmin(admin.ModelAdmin):
    list_display = ('turma', 'data_aula', 'autor', 'publicado_em')
    list_filter = ('turma',)
    search_fields = ('conteudo', 'tarefa_descricao')

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'usuario__is_active', 'criado_em')
    list_filter = ('tipo', 'usuario__is_active')
    filter_horizontal = ('alunos',)