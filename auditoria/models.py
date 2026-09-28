from django.conf import settings
from django.db import models


class Evento(models.Model):
    # O que o sistema registra. Nunca senha, nunca token.
    class Acao(models.TextChoices):
        LOGIN = 'LOGIN', 'Entrou no sistema'
        LOGIN_FALHA = 'LOGIN_FALHA', 'Erro ao entrar'
        ACESSO_APROVADO = 'ACESSO_APROVADO', 'Aprovou pedido de acesso'
        ACESSO_RECUSADO = 'ACESSO_RECUSADO', 'Recusou pedido de acesso'
        RELATORIO_PUBLICADO = 'RELATORIO_PUBLICADO', 'Publicou relatório'
        EMAIL = 'EMAIL', 'Aviso por e-mail'

    acao = models.CharField(max_length=30, choices=Acao.choices)
    # SET_NULL: se a conta for eliminada, a linha do log continua,
    # só que sem apontar para ninguém.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos',
    )
    # O que foi digitado no campo usuário quando o login falhou.
    usuario_informado = models.CharField(max_length=150, blank=True)
    detalhe = models.CharField(max_length=255, blank=True)
    quando = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-quando']
        verbose_name = 'evento'
        verbose_name_plural = 'eventos'

    def __str__(self):
        quem = self.usuario or self.usuario_informado or 'desconhecido'
        return f'{quem} - {self.get_acao_display()}'