from django import forms
from .models import RelatorioDiario


class RelatorioDiarioForm(forms.ModelForm):
    class Meta:
        model = RelatorioDiario
        fields = ['turma', 'data_aula', 'conteudo', 'tarefa_descricao', 'tarefa_data_entrega', 'observacoes', 'autor']