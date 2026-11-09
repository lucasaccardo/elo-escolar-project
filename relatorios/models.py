from django.db import models
from django.conf import settings

class Turma(models.Model):  # Para representar uma turma de alunos
    nome = models.CharField(max_length=100)
    ano_letivo = models.IntegerField()
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='turmas'
    )

    def __str__(self):
        return self.nome

class Aluno(models.Model):
    nome_completo = models.CharField(max_length=255)
    rgm = models.CharField(max_length=20, unique=True)
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.nome_completo} (RGM: {self.rgm})"

class RelatorioDiario(models.Model):  # Para representar o relatório diário de uma turma
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT)
    data_aula = models.DateField()
    conteudo = models.TextField()
    tarefa_descricao = models.TextField(blank=True)
    tarefa_data_entrega = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='relatorios'
    )
    publicado_em = models.DateTimeField(auto_now_add=True)

    # --- Marca de edição (RF11) ---------------------------------------
    # Nulo quer dizer "nunca foi editado". É a forma honesta de dizer isso
    # no banco: uma data qualquer aqui seria mentira. Por isso tambem NAO
    # se usa auto_now, que gravaria a data a cada save(), inclusive quando
    # o que mudou foi so a marca de exclusao.
    editado_em = models.DateTimeField(null=True, blank=True)
    editado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='relatorios_editados',
    )

    # --- Exclusão lógica (RF11) ---------------------------------------
    # O registro nao sai do banco: so deixa de aparecer. O historico
    # sobrevive, a auditoria continua fazendo sentido e um engano pode ser
    # desfeito.
    excluido = models.BooleanField(default=False)
    excluido_em = models.DateTimeField(null=True, blank=True)
    excluido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='relatorios_excluidos',
    )

    class Meta:
        ordering = ['-data_aula']

    def __str__(self):
        return f'{self.turma} - {self.data_aula}'

    @property
    def foi_editado(self):
        """Serve ao template: mostra o selo de alteracao ou nao."""
        return self.editado_em is not None

class Perfil(models.Model):

    class Tipo(models.TextChoices):
        ESCOLA = 'escola', 'Escola (institucional)'
        DIRETOR = 'diretor', 'Diretor'
        COORDENADOR = 'coordenador', 'Coordenador'
        PROFESSOR = 'professor', 'Professor'
        RESPONSAVEL = 'responsavel', 'Responsável'

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil'
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    alunos = models.ManyToManyField(Aluno, blank=True, related_name='responsaveis')
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.usuario.username} ({self.get_tipo_display()})'