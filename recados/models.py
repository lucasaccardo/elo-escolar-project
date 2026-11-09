from datetime import date

from django.conf import settings
from django.db import models

from relatorios.models import Turma


class Recado(models.Model):
    """RF09 - aviso da escola para as familias.

    Diferenca para o relatorio diario: o relatorio fala do que aconteceu numa
    aula e pertence sempre a uma turma. O recado fala do que vai acontecer e
    pode ser de uma turma OU da escola inteira - por isso o campo turma aceita
    nulo.
    """

    # null=True e o que permite o recado geral, dirigido a escola toda.
    turma = models.ForeignKey(
        Turma,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='recados',
        help_text='Em branco significa recado para a escola inteira.',
    )
    titulo = models.CharField(max_length=120)
    mensagem = models.TextField()
    # Nulo quer dizer "sem prazo": o recado fica no ar ate alguem tirar.
    exibir_ate = models.DateField(
        null=True,
        blank=True,
        help_text='Depois dessa data o recado sai do mural das famílias. '
                  'Deixe em branco para não ter prazo.',
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='recados',
    )
    publicado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-publicado_em']
        verbose_name = 'recado'
        verbose_name_plural = 'recados'

    def __str__(self):
        destino = self.turma.nome if self.turma_id else 'Escola inteira'
        return f'{destino} - {self.titulo}'

    @property
    def eh_geral(self):
        """Serve ao template: recado sem turma vale para a escola toda."""
        return self.turma_id is None

    @property
    def esta_no_ar(self):
        """Sem prazo, ou com prazo que ainda nao venceu."""
        return self.exibir_ate is None or self.exibir_ate >= date.today()
