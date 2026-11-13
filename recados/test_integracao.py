"""Testes de INTEGRACAO do mural de recados (RF09).

Banco de teste de verdade, requisicao entrando pela URL e atravessando
middleware, view, permissoes e ORM. Nada e substituido por duble.
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from django.urls import reverse

from acessos.models import VERSAO_TERMOS, AceiteTermos
from auditoria.models import Evento
from recados.models import Recado
from relatorios.models import Aluno, Perfil, Turma

User = get_user_model()


# A etiqueta vale tambem para as classes que herdam desta: no Django, a
# marcacao e herdada pelas subclasses. Por isso basta etiquetar a base.
@tag('integracao')
class BaseDeRecados(TestCase):
    """Uma escola com duas turmas e uma familia ligada a apenas uma delas."""

    def setUp(self):
        self.professora = self._criar('marcia.silva', Perfil.Tipo.PROFESSOR)
        self.coordenador = self._criar('joao.pereira', Perfil.Tipo.COORDENADOR)
        self.responsavel = self._criar('ana.souza', Perfil.Tipo.RESPONSAVEL)

        self.turma = Turma.objects.create(
            nome='3 ANO C', ano_letivo=2026, professor=self.professora,
        )
        self.outra_turma = Turma.objects.create(
            nome='5 ANO A', ano_letivo=2026, professor=self.coordenador,
        )
        self.aluno = Aluno.objects.create(
            nome_completo='Pedro Souza', rgm='2026001', turma=self.turma,
        )
        self.responsavel.perfil.alunos.add(self.aluno)

    def _criar(self, usuario, tipo):
        pessoa = User.objects.create_user(
            username=usuario,
            email=f'{usuario}@example.com',
            password='senha-de-teste-123',
            first_name=usuario.split('.')[0].capitalize(),
            last_name='Teste',
        )
        Perfil.objects.create(usuario=pessoa, tipo=tipo)
        # Sem o aceite, o middleware ExigirAceiteTermos bloqueia tudo.
        AceiteTermos.objects.create(usuario=pessoa, versao=VERSAO_TERMOS)
        return pessoa

    def entrar_como(self, pessoa):
        self.client.force_login(pessoa)

    def recado(self, titulo, turma, dias_de_prazo=None, autor=None):
        prazo = None
        if dias_de_prazo is not None:
            prazo = date.today() + timedelta(days=dias_de_prazo)
        return Recado.objects.create(
            turma=turma,
            titulo=titulo,
            mensagem=f'Corpo do recado: {titulo}.',
            exibir_ate=prazo,
            autor=autor or self.coordenador,
        )


class MuralDoResponsavelTest(BaseDeRecados):
    """O que a familia enxerga, e o que nao enxerga."""

    def test_responsavel_ve_recado_geral_e_o_da_turma_do_filho(self):
        # Caminho feliz: status e corpo.
        self.recado('Reuniao de pais', turma=None)
        self.recado('Prova de matematica', turma=self.turma)
        self.entrar_como(self.responsavel)

        resposta = self.client.get(reverse('lista_recados'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Reuniao de pais')
        self.assertContains(resposta, 'Prova de matematica')

    def test_responsavel_nao_ve_recado_de_turma_alheia(self):
        # Seguranca: a regra de visibilidade atravessando a pilha ate o banco.
        self.recado('Passeio do 5 ANO A', turma=self.outra_turma)
        self.entrar_como(self.responsavel)

        resposta = self.client.get(reverse('lista_recados'))

        self.assertNotContains(resposta, 'Passeio do 5 ANO A')

    def test_responsavel_nao_ve_recado_com_prazo_vencido(self):
        # A regra do periodo de exibicao funcionando de verdade, nao so na
        # aparencia: o recado vencido nem chega ao template.
        self.recado('Festa junina', turma=self.turma, dias_de_prazo=-1)
        self.entrar_como(self.responsavel)

        resposta = self.client.get(reverse('lista_recados'))

        self.assertNotContains(resposta, 'Festa junina')

    def test_responsavel_ve_recado_cujo_prazo_vence_hoje(self):
        # Fronteira da regra: hoje ainda conta.
        self.recado('Entrega do livro', turma=self.turma, dias_de_prazo=0)
        self.entrar_como(self.responsavel)

        resposta = self.client.get(reverse('lista_recados'))

        self.assertContains(resposta, 'Entrega do livro')

    def test_responsavel_nao_abre_o_formulario_de_recado(self):
        # Seguranca: autenticado, porem sem permissao para esta acao.
        self.entrar_como(self.responsavel)

        resposta = self.client.get(reverse('cadastrar_recado'))

        self.assertEqual(resposta.status_code, 403)
        self.assertContains(resposta, 'Forbidden', status_code=403)

    def test_visitante_anonimo_e_mandado_para_o_login(self):
        resposta = self.client.get(reverse('lista_recados'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])


class MuralDaEquipeTest(BaseDeRecados):
    """A equipe da escola enxerga tambem o que ja saiu do ar."""

    def test_professora_ve_recado_encerrado_com_o_aviso(self):
        self.recado('Festa junina', turma=self.turma, dias_de_prazo=-1)
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('lista_recados'))

        self.assertContains(resposta, 'Festa junina')
        self.assertContains(resposta, 'Encerrado em')


class PublicarRecadoTest(BaseDeRecados):
    """Quem publica o que, e o que fica gravado."""

    def dados(self, **troca):
        valores = {
            'turma': self.turma.id,
            'titulo': 'Reuniao de pais na quinta',
            'mensagem': 'A reuniao comeca as 19h, no patio coberto.',
            'exibir_ate': '',
        }
        valores.update(troca)
        return valores

    def test_professora_abre_o_formulario(self):
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('cadastrar_recado'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Título do recado')

    def test_professora_publica_recado_da_turma_dela(self):
        # Caminho feliz do POST com efeito persistido.
        self.entrar_como(self.professora)

        resposta = self.client.post(reverse('cadastrar_recado'), self.dados())

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('lista_recados'))

        gravado = Recado.objects.get(titulo='Reuniao de pais na quinta')
        self.assertEqual(gravado.turma, self.turma)
        # A autoria vem da sessao, nunca do formulario.
        self.assertEqual(gravado.autor, self.professora)

    def test_professora_nao_publica_recado_para_a_escola_inteira(self):
        # A regra de negocio que separa as duas permissoes. Mesmo enviando o
        # campo turma vazio na marra, o formulario recusa.
        self.entrar_como(self.professora)

        resposta = self.client.post(
            reverse('cadastrar_recado'), self.dados(turma=''),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'coordenação ou pela direção')
        self.assertEqual(Recado.objects.count(), 0)

    def test_coordenador_publica_recado_para_a_escola_inteira(self):
        # O contraponto: para a gestao, turma em branco e valido e significa
        # "escola inteira".
        self.entrar_como(self.coordenador)

        resposta = self.client.post(
            reverse('cadastrar_recado'),
            self.dados(turma='', titulo='Recesso na proxima sexta'),
        )

        self.assertEqual(resposta.status_code, 302)

        gravado = Recado.objects.get(titulo='Recesso na proxima sexta')
        self.assertIsNone(gravado.turma)
        self.assertTrue(gravado.eh_geral)

    def test_turma_alheia_forjada_no_envio_e_recusada(self):
        # Cenario de erro: a professora tenta mandar recado para a turma do
        # coordenador. O queryset restrito do formulario barra.
        self.entrar_como(self.professora)

        resposta = self.client.post(
            reverse('cadastrar_recado'), self.dados(turma=self.outra_turma.id),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Recado.objects.count(), 0)

    def test_recado_sem_titulo_nao_e_gravado(self):
        # Cenario de erro: campo obrigatorio vazio.
        self.entrar_como(self.professora)

        resposta = self.client.post(
            reverse('cadastrar_recado'), self.dados(titulo=''),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Recado.objects.count(), 0)

    def test_a_auditoria_registra_a_publicacao(self):
        # Rastreabilidade.
        self.entrar_como(self.coordenador)

        self.client.post(reverse('cadastrar_recado'), self.dados())

        self.assertEqual(
            Evento.objects.filter(
                acao=Evento.Acao.RECADO_PUBLICADO,
                usuario=self.coordenador,
            ).count(),
            1,
        )
