# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Formulario da solicitacao, que limita a escolha
#                      aos alunos do proprio responsavel.
#   REQUISITOS.......: RF10
#   PROCURE POR......: SolicitacaoForm, queryset, validacao, alunos do
#                      responsavel
# ----------------------------------------------------------------------

from django import forms

from .models import Solicitacao


class SolicitacaoForm(forms.ModelForm):
    """Formulário da família: abre a solicitação."""

    class Meta:
        model = Solicitacao
        fields = ['aluno', 'tipo', 'assunto', 'descricao']

        labels = {
            'aluno': 'Sobre qual estudante',
            'tipo': 'Tipo da solicitação',
            'assunto': 'Assunto',
            'descricao': 'Descrição',
        }

        help_texts = {
            'descricao': 'Descreva o pedido. Não registre informações de '
                         'saúde ou condições clínicas nesta tela.',
        }

        widgets = {
            'aluno': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'assunto': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: Falta na segunda-feira',
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 5,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['aluno'].empty_label = '— Selecione o estudante —'
        self.fields['tipo'].choices = [
            ('', '— Selecione o tipo —'),
        ] + list(Solicitacao.Tipo.choices)


class RespostaForm(forms.Form):
    """Formulário da escola: responde a solicitação.

    Não é um ModelForm de propósito. A resposta não é apenas gravar um
    campo: ela muda a situação, carimba data e autor e dispara um aviso.
    Esse conjunto vive no método responder() do model, e o formulário só
    precisa validar o texto.
    """

    texto = forms.CharField(
        label='Resposta da escola',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        help_text='A família recebe esta resposta por e-mail e no sistema.',
    )

    def clean_texto(self):
        texto = self.cleaned_data['texto'].strip()
        if len(texto) < 10:
            raise forms.ValidationError(
                'Escreva uma resposta com pelo menos 10 caracteres. '
                'Uma resposta vazia ou de uma palavra não informa a família.'
            )
        return texto
