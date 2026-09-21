from django.conf import settings
from django.db import models


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