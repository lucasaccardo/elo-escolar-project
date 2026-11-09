from django import forms

from .models import Recado


class RecadoForm(forms.ModelForm):
    class Meta:
        model = Recado
        fields = ['turma', 'titulo', 'mensagem', 'exibir_ate']

        labels = {
            'turma': 'Turma',
            'titulo': 'Título do recado',
            'mensagem': 'Mensagem',
            'exibir_ate': 'Exibir até',
        }

        widgets = {
            'turma': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: Reunião de pais na quinta-feira',
            }),
            'mensagem': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 5,
            }),
            'exibir_ate': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date',
            }),
        }

    def __init__(self, *args, pode_falar_pela_escola=False, **kwargs):
        """O formulario muda conforme quem esta na tela.

        Quem nao fala pela escola nao recebe a opcao "escola inteira" - ela
        simplesmente nao existe no campo. Mas a regra tambem e conferida no
        clean_turma, porque esconder opcao na tela nao e seguranca: qualquer
        pessoa pode enviar um formulario forjado.
        """
        super().__init__(*args, **kwargs)
        self.pode_falar_pela_escola = pode_falar_pela_escola

        # required fica SEMPRE False de proposito. Se fosse True para o
        # professor, o Django responderia "Este campo e obrigatorio" antes de
        # chegar ao clean_turma, e a pessoa nunca leria a explicacao da regra.
        # Quem recusa e o clean_turma, com a frase que ensina o porque.
        self.fields['turma'].required = False

        if pode_falar_pela_escola:
            self.fields['turma'].empty_label = '— Escola inteira —'
            self.fields['turma'].help_text = (
                'Deixe em branco para avisar a escola inteira.'
            )
        else:
            self.fields['turma'].empty_label = '— Selecione a turma —'
            self.fields['turma'].help_text = (
                'O recado vai para as famílias desta turma.'
            )

    def clean_turma(self):
        turma = self.cleaned_data.get('turma')

        if turma is None and not self.pode_falar_pela_escola:
            raise forms.ValidationError(
                'Escolha uma turma. Recado para a escola inteira só pode ser '
                'publicado pela coordenação ou pela direção.'
            )

        return turma
