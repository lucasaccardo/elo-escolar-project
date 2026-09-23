from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from relatorios.models import Aluno

from .models import SolicitacaoAcesso

User = get_user_model()


class CadastroResponsavelForm(forms.Form):
    nome = forms.CharField(label='Nome', max_length=150)
    sobrenome = forms.CharField(label='Sobrenome', max_length=150)
    email = forms.EmailField(
        label='E-mail',
        help_text='É com este e-mail que você vai entrar no sistema.',
    )
    senha = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='No mínimo 8 caracteres, sem ser só números.',
    )
    confirmar_senha = forms.CharField(
        label='Confirme a senha',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    rgm = forms.CharField(
        label='RGM do aluno',
        max_length=20,
        help_text='Número de matrícula. Se não souber, peça à secretaria.',
    )
    aceite_termos = forms.BooleanField(
        label='Li e aceito os Termos de Uso e estou ciente '
              'da Política de Privacidade.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dá a aparência do Bootstrap a todos os campos de uma vez.
        for nome_campo, campo in self.fields.items():
            if nome_campo == 'aceite_termos':
                campo.widget.attrs['class'] = 'form-check-input'
            else:
                campo.widget.attrs['class'] = 'form-control'

    def clean_email(self):
        # O e-mail vira o nome de usuário, então não pode repetir.
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError('Este e-mail já está cadastrado.')
        return email

    def clean_rgm(self):
        # Só confere se o RGM existe. Nunca mostra o nome da criança.
        rgm = self.cleaned_data['rgm'].strip()
        try:
            self.aluno = Aluno.objects.get(rgm=rgm)
        except Aluno.DoesNotExist:
            raise forms.ValidationError(
                'RGM não encontrado. Confira o número com a secretaria.'
            )
        return rgm

    def clean(self):
        dados = super().clean()
        senha = dados.get('senha')
        if senha and senha != dados.get('confirmar_senha'):
            self.add_error('confirmar_senha', 'As senhas não conferem.')
        elif senha:
            # Usa as mesmas regras de senha do settings.py.
            try:
                validate_password(senha)
            except forms.ValidationError as erro:
                self.add_error('senha', erro)
        return dados


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Usuário ou senha inválidos.',
    }

    def clean(self):
        # Responsável entra pelo e-mail, que foi gravado em minúsculas.
        usuario = self.cleaned_data.get('username', '')
        if '@' in usuario:
            self.cleaned_data['username'] = usuario.strip().lower()

        try:
            return super().clean()
        except forms.ValidationError:
            mensagem = self._mensagem_conta_desligada()
            if mensagem:
                raise forms.ValidationError(mensagem, code='inactive')
            raise

    def _mensagem_conta_desligada(self):
        # Só explica o motivo para quem acertou a senha. Para os outros,
        # continua "Usuário ou senha inválidos." e ninguém descobre contas.
        usuario = User.objects.filter(
            username=self.cleaned_data.get('username'),
            is_active=False,
        ).first()
        if usuario is None:
            return None
        if not usuario.check_password(self.cleaned_data.get('password')):
            return None

        pedidos = usuario.solicitacoes_acesso
        if pedidos.filter(status=SolicitacaoAcesso.Status.PENDENTE).exists():
            return 'Seu cadastro está aguardando a aprovação da escola.'
        if pedidos.filter(status=SolicitacaoAcesso.Status.RECUSADA).exists():
            return ('Seu pedido de acesso foi recusado. '
                    'Procure a secretaria da escola.')
        return 'Acesso desativado. Procure a secretaria da escola.'