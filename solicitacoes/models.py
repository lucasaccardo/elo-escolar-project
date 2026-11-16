from django.conf import settings
from django.db import models
from django.utils import timezone

from relatorios.models import Aluno


class Solicitacao(models.Model):
    """RF10 - pedido que a familia faz a escola, com acompanhamento.

    Diferenca para o recado e para o relatorio: estes vao da escola para a
    familia e terminam quando sao publicados. A solicitacao vai no sentido
    contrario e nao termina ao ser aberta - ela tem situacao, que muda ao
    longo do caminho. E justamente a falta desse acompanhamento, no grupo de
    mensagens, que o projeto se propoe a resolver.
    """

    class Tipo(models.TextChoices):
        JUSTIFICATIVA = 'justificativa', 'Justificativa de falta'
        CONTATO = 'contato', 'Pedido de contato'
        DUVIDA = 'duvida', 'Dúvida'

    class Situacao(models.TextChoices):
        ABERTA = 'aberta', 'Aberta'
        RESPONDIDA = 'respondida', 'Respondida'
        ENCERRADA = 'encerrada', 'Encerrada'

    # A solicitacao pertence a uma crianca, e e por ela que a escola sabe
    # qual turma, e portanto qual professor, deve responder.
    aluno = models.ForeignKey(
        Aluno,
        on_delete=models.PROTECT,
        related_name='solicitacoes',
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='solicitacoes_abertas',
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    assunto = models.CharField(max_length=120)
    descricao = models.TextField()
    situacao = models.CharField(
        max_length=20,
        choices=Situacao.choices,
        default=Situacao.ABERTA,
    )
    aberta_em = models.DateTimeField(auto_now_add=True)

    # Nulo enquanto a escola nao respondeu. A ausencia de valor e a forma
    # honesta de dizer que ainda nao houve resposta.
    resposta = models.TextField(blank=True)
    respondida_em = models.DateTimeField(null=True, blank=True)
    respondida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitacoes_respondidas',
    )
    encerrada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-aberta_em']
        verbose_name = 'solicitação'
        verbose_name_plural = 'solicitações'

    def __str__(self):
        return f'{self.aluno.nome_completo} - {self.assunto}'

    @property
    def esta_aberta(self):
        return self.situacao == self.Situacao.ABERTA

    @property
    def foi_respondida(self):
        return self.respondida_em is not None

    def responder(self, usuario, texto):
        """Grava a resposta da escola e muda a situacao.

        A regra de quem pode responder NAO mora aqui: mora em
        permissions.py, como no resto do sistema. Este metodo apenas
        executa, depois que a view perguntou e recebeu autorizacao.
        """
        self.resposta = texto
        self.respondida_por = usuario
        self.respondida_em = timezone.now()
        self.situacao = self.Situacao.RESPONDIDA
        self.save(update_fields=[
            'resposta', 'respondida_por', 'respondida_em', 'situacao',
        ])

    def encerrar(self):
        """Quem abriu dá o assunto por resolvido."""
        self.situacao = self.Situacao.ENCERRADA
        self.encerrada_em = timezone.now()
        self.save(update_fields=['situacao', 'encerrada_em'])
