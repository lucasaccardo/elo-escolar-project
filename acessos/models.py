import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class SolicitacaoAcesso(models.Model):
    # Os 3 estados possíveis de um pedido.
    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        APROVADA = 'APROVADA', 'Aprovada'
        RECUSADA = 'RECUSADA', 'Recusada'

    # Quem pediu. A conta nasce desativada.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='solicitacoes_acesso',
    )
    # Para qual criança. Vem da busca pelo RGM.
    aluno = models.ForeignKey(
        'relatorios.Aluno',
        on_delete=models.PROTECT,
        related_name='solicitacoes_acesso',
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    # Quando aceitou os Termos de Uso. Sem aceite, não há pedido.
    aceite_termos_em = models.DateTimeField()
    criado_em = models.DateTimeField(auto_now_add=True)

    # Só são preenchidos quando alguém aprova ou recusa.
    analisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='solicitacoes_analisadas',
    )
    analisado_em = models.DateTimeField(null=True, blank=True)
    justificativa = models.TextField(blank=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'solicitação de acesso'
        verbose_name_plural = 'solicitações de acesso'

    def __str__(self):
        return f'{self.usuario} - {self.aluno} ({self.get_status_display()})'


# Versao vigente dos Termos de Uso. Trocar esta linha quando o texto mudar
# faz o sistema pedir um novo aceite a todo mundo.
VERSAO_TERMOS = '2026-09-21'


class AceiteTermos(models.Model):
    """Prova de que um usuario aceitou os Termos, e de qual versao."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='aceites',
    )
    versao = models.CharField(max_length=20)
    aceito_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Uma conta so aceita a mesma versao uma vez.
        unique_together = ('usuario', 'versao')
        ordering = ['-aceito_em']
        verbose_name = 'aceite dos termos'
        verbose_name_plural = 'aceites dos termos'

    def __str__(self):
        return f'{self.usuario} aceitou a versao {self.versao}'


# Quanto tempo o código vale, e quantas tentativas são aceitas. Os dois
# números limitam a janela de ataque: sem prazo, um código vazado serviria
# para sempre; sem limite de tentativas, seria possível tentar os um milhão
# de códigos possíveis.
VALIDADE_DO_CODIGO_MINUTOS = 15
MAXIMO_DE_TENTATIVAS = 5


class ConfirmacaoEmail(models.Model):
    """RF14 - prova de que o e-mail informado no cadastro é mesmo da pessoa.

    Existe porque o e-mail é o login do responsável e o canal por onde ele
    recebe a aprovação e a ligação de troca de senha. Um erro de digitação
    no cadastro entregaria tudo isso a um estranho.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='confirmacao_email',
    )
    # O código NÃO é guardado em texto. Vale o mesmo raciocínio da senha:
    # quem lê o banco não pode usar o que encontra ali.
    codigo_hash = models.CharField(max_length=128)
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    tentativas = models.PositiveSmallIntegerField(default=0)
    confirmado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'confirmação de e-mail'
        verbose_name_plural = 'confirmações de e-mail'

    def __str__(self):
        estado = 'confirmado' if self.confirmado else 'pendente'
        return f'{self.usuario.email} ({estado})'

    @property
    def confirmado(self):
        return self.confirmado_em is not None

    @property
    def expirou(self):
        return timezone.now() > self.expira_em

    @property
    def esgotou_tentativas(self):
        return self.tentativas >= MAXIMO_DE_TENTATIVAS

    @classmethod
    def gerar(cls, usuario):
        """Cria ou renova a confirmação e devolve o código em texto.

        O código em texto existe apenas nesta chamada, o tempo de ser
        enviado por e-mail. Depois disso, só o resumo criptográfico fica.
        """
        # secrets, e não random: o módulo random é previsível e não serve
        # para nada que precise resistir a adivinhação.
        codigo = f'{secrets.randbelow(1000000):06d}'
        confirmacao, _ = cls.objects.update_or_create(
            usuario=usuario,
            defaults={
                'codigo_hash': make_password(codigo),
                'expira_em': timezone.now() + timedelta(
                    minutes=VALIDADE_DO_CODIGO_MINUTOS),
                'tentativas': 0,
                'confirmado_em': None,
            },
        )
        return confirmacao, codigo

    def conferir(self, codigo):
        """Devolve (deu_certo, motivo). Cada tentativa é contada."""
        if self.confirmado:
            return True, 'já confirmado'
        if self.expirou:
            return False, 'expirado'
        if self.esgotou_tentativas:
            return False, 'tentativas esgotadas'

        self.tentativas += 1
        if not check_password(codigo, self.codigo_hash):
            self.save(update_fields=['tentativas'])
            return False, 'codigo incorreto'

        self.confirmado_em = timezone.now()
        self.save(update_fields=['tentativas', 'confirmado_em'])
        return True, 'confirmado'


def confirmacao_pendente(usuario):
    """Diz se este cadastro parou no meio, antes de confirmar o e-mail.

    Serve para desfazer um beco sem saída: quem fecha o navegador antes de
    digitar o código perde a sessão, não consegue entrar (a conta nasce
    desligada) e não consegue recuperar a senha (o Django só envia a
    ligação para conta ativa). Sem isto, a única saída seria ligar para a
    escola.

    Repare que a conta precisa estar DESLIGADA e com pedido ainda
    PENDENTE. Conta aprovada, recusada ou já confirmada não entra aqui:
    nesses casos o cadastro realmente já existe e deve ser recusado.
    """
    if usuario.is_active:
        return False

    confirmacao = ConfirmacaoEmail.objects.filter(usuario=usuario).first()
    # Cadastro feito antes do RF14 nem tem registro de confirmação; ele
    # também conta como pendente.
    if confirmacao is not None and confirmacao.confirmado:
        return False

    return SolicitacaoAcesso.objects.filter(
        usuario=usuario,
        status=SolicitacaoAcesso.Status.PENDENTE,
    ).exists()


# Quantas tentativas erradas são aceitas antes do bloqueio, e por quanto
# tempo ele dura. O limite por conta é o que de fato protege a senha; o
# limite por origem é defesa secundária, contra quem varre várias contas a
# partir do mesmo lugar.
JANELA_DE_BLOQUEIO_MINUTOS = 15
TENTATIVAS_POR_CONTA = 5
TENTATIVAS_POR_ORIGEM = 20


class TentativaDeLogin(models.Model):
    """Registro das tentativas de entrada malsucedidas.

    Existe para impedir adivinhação de senha por tentativa e erro. Sem
    limite, um programa simples percorre listas de senhas comuns até
    acertar, e nenhuma política de senha forte resolve isso sozinha.

    Fica no banco, e não em memória, por uma razão concreta: o servidor
    roda mais de um processo, e contador em memória seria contado em
    separado por cada um - o que multiplicaria o limite pelo número de
    processos sem ninguém perceber.

    O que se guarda é o identificador DIGITADO, não o usuário: a tentativa
    pode ser contra uma conta que nem existe, e esse caso também interessa.
    Senha nunca é gravada aqui, em nenhuma circunstância.
    """

    identificador = models.CharField(max_length=150)
    origem = models.GenericIPAddressField(null=True, blank=True)
    em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'tentativa de login'
        verbose_name_plural = 'tentativas de login'
        indexes = [
            models.Index(fields=['identificador', 'em']),
            models.Index(fields=['origem', 'em']),
        ]

    def __str__(self):
        return f'{self.identificador} em {self.em:%d/%m/%Y %H:%M}'

    # ------------------------------------------------------------------
    @staticmethod
    def _inicio_da_janela():
        return timezone.now() - timedelta(minutes=JANELA_DE_BLOQUEIO_MINUTOS)

    @classmethod
    def registrar_falha(cls, identificador, origem):
        return cls.objects.create(
            identificador=identificador[:150], origem=origem,
        )

    @classmethod
    def esquecer(cls, identificador, origem):
        """Entrada bem-sucedida zera o contador daquela conta.

        Sem isto, quem erra quatro vezes, acerta, e erra mais uma no dia
        seguinte seria bloqueado por tentativas que já não dizem nada.
        """
        cls.objects.filter(identificador=identificador[:150]).delete()
        if origem:
            cls.objects.filter(origem=origem).delete()

    @classmethod
    def bloqueado(cls, identificador, origem):
        """Diz se esta tentativa deve ser recusada antes de conferir a senha.

        A conferência vem ANTES da autenticação de propósito: assim o
        tempo de resposta não varia conforme a senha estar certa ou
        errada, e o bloqueio não vira um jeito de descobrir isso.
        """
        desde = cls._inicio_da_janela()

        por_conta = cls.objects.filter(
            identificador=identificador[:150], em__gte=desde,
        ).count()
        if por_conta >= TENTATIVAS_POR_CONTA:
            return True

        if origem:
            por_origem = cls.objects.filter(
                origem=origem, em__gte=desde,
            ).count()
            if por_origem >= TENTATIVAS_POR_ORIGEM:
                return True

        return False
