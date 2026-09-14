from django import forms
from .models import RelatorioDiario


class RelatorioDiarioForm(forms.ModelForm):
    class Meta:
        model = RelatorioDiario
        fields = ['turma', 'data_aula', 'conteudo', 'tarefa_descricao',
                  'tarefa_data_entrega', 'observacoes']

        labels = {
            'turma': 'Turma',
            'data_aula': 'Data da aula',
            'conteudo': 'Conteúdo trabalhado',
            'tarefa_descricao': 'Tarefa de casa',
            'tarefa_data_entrega': 'Data de entrega da tarefa',
            'observacoes': 'Observações',
        }

        widgets = {
            'turma': forms.Select(attrs={'class': 'form-select'}),
            'data_aula': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'conteudo': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'tarefa_descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tarefa_data_entrega': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }