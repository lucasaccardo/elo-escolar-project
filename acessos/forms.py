from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from relatorios.models import Aluno

from auditoria.models import Evento
from auditoria.services import registrar

from .models import (
    JANELA_DE_BLOQUEIO_MINUTOS,
    SolicitacaoAcesso,
    TentativaDeLogin,
    confirmacao_pendente,
)

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
        # Marca todos os campos de uma vez com as classes que o estilo.css usa.
        for nome_campo, campo in self.fields.items():
            if nome_campo == 'aceite_termos':
                campo.widget.attrs['class'] = 'form-check-input'
            else:
                campo.widget.attrs['class'] = 'form-control'

    # Preenchido quando o e-mail pertence a um cadastro que parou antes da
    # confirmação. A view lê este atributo e retoma de onde parou.
    usuario_pendente = None

    def clean_email(self):
        # O e-mail vira o nome de usuário, então não pode repetir.
        email = self.cleaned_data['email'].lower()
        usuario = User.objects.filter(username=email).first()
        if usuario is None:
            return email

        if confirmacao_pendente(usuario):
            # Não é um cadastro repetido: é o mesmo cadastro, inacabado.
            # Nada da conta é alterado aqui - nem a senha. Alterar seria
            # abrir uma porta para outra pessoa trocar a senha de uma conta
            # que ainda não é de ninguém, e depois herdá-la aprovada.
            self.usuario_pendente = usuario
            return email

        raise forms.ValidationError('Este e-mail já está cadastrado.')

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


def origem_da_requisicao(request):
    """Descobre de onde veio a requisição.

    Atrás do servidor de publicação, o endereço que chega em REMOTE_ADDR é
    o do próprio servidor, e o do visitante vem em X-Forwarded-For. Por
    isso o cabeçalho é lido primeiro.

    Ele PODE ser forjado por quem monta a requisição à mão, e é justamente
    por isso que o limite por origem é defesa secundária. O limite que
    protege a senha é o por conta, que não depende de cabeçalho algum: o
    identificador digitado é o que o atacante precisa acertar, e falsificá-lo
    equivale a desistir de atacar aquela conta.
    """
    if request is None:
        return None
    encaminhado = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if encaminhado:
        return encaminhado.split(',')[0].strip()[:45] or None
    return request.META.get('REMOTE_ADDR') or None


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Usuário ou senha inválidos.',
        'bloqueado': (
            'Muitas tentativas seguidas. Aguarde '
            f'{JANELA_DE_BLOQUEIO_MINUTOS} minutos e tente de novo, ou use '
            '"Esqueci minha senha".'
        ),
    }

    def clean(self):
        # Responsável entra pelo e-mail, que foi gravado em minúsculas.
        usuario = self.cleaned_data.get('username', '')
        if '@' in usuario:
            usuario = usuario.strip().lower()
            self.cleaned_data['username'] = usuario

        origem = origem_da_requisicao(self.request)

        # A conferência do bloqueio vem ANTES de qualquer tentativa de
        # autenticar: é o que impede a adivinhação por tentativa e erro, e
        # também o que mantém o tempo de resposta igual nos dois casos.
        if TentativaDeLogin.bloqueado(usuario, origem):
            registrar(
                Evento.Acao.LOGIN_BLOQUEADO,
                usuario_informado=usuario,
                detalhe=f'origem {origem or "desconhecida"}',
            )
            raise forms.ValidationError(
                self.error_messages['bloqueado'], code='bloqueado',
            )

        try:
            dados = super().clean()
        except forms.ValidationError:
            TentativaDeLogin.registrar_falha(usuario, origem)
            mensagem = self._mensagem_conta_desligada()
            if mensagem:
                raise forms.ValidationError(mensagem, code='inactive')
            raise

        # Entrou: o contador daquela conta deixa de fazer sentido.
        TentativaDeLogin.esquecer(usuario, origem)
        return dados

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


class CodigoForm(forms.Form):
    """Código de seis dígitos da confirmação de e-mail (RF14)."""

    codigo = forms.CharField(
        label='Código de seis dígitos',
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code',
            'placeholder': '000000',
        }),
    )

    def clean_codigo(self):
        codigo = self.cleaned_data['codigo'].strip()
        if not codigo.isdigit() or len(codigo) != 6:
            raise forms.ValidationError(
                'O código tem exatamente seis dígitos.'
            )
        return codigo
