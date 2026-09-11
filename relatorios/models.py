from django.db import models
from django.conf import settings



class Turma(models.Model): #Para representar uma turma de alunos
    nome = models.CharField(max_length=100)
    ano_letivo = models.IntegerField()

    def __str__(self):
        return self.nome


class RelatorioDiario(models.Model): #Para representar o relatório diário de uma turma
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT)
    data_aula = models.DateField()
    conteudo = models.TextField()
    tarefa_descricao = models.TextField(blank=True)
    tarefa_data_entrega = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    publicado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_aula']

    def __str__(self):
        return f'{self.turma} - {self.data_aula}'