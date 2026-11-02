"""Testes de INTEGRACAO das rotas de relatorios.

Diferenca para os testes unitarios que ja existem em tests.py:

  - la usamos SimpleTestCase, que PROIBE o banco, e trocamos tudo por dubles;
  - aqui usamos TestCase, que CRIA um banco de teste de verdade, e nao trocamos
    nada: a requisicao entra pela URL, passa pelos middlewares, pela view, pelas
    regras de permissao, pelo ORM e chega ao banco.

O banco de teste e criado antes da suite e apagado no fim. Cada teste roda dentro
de uma transacao que e desfeita ao terminar, entao nenhum teste enxerga o que o
outro gravou.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from acessos.models import VERSAO_TERMOS, AceiteTermos
from relatorios.models import Aluno, Perfil, RelatorioDiario, Turma

User = get_user_model()


class BaseDeIntegracao(TestCase):
    """Monta o cenario comum: uma escola pequena, com gente de cada perfil."""

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
        # A filha do responsavel: e por ela que ele enxerga a turma.
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
        # Sem este registro o middleware ExigirAceiteTermos bloqueia tudo.
        AceiteTermos.objects.create(usuario=pessoa, versao=VERSAO_TERMOS)
        return pessoa

    def entrar_como(self, pessoa):
        self.client.force_login(pessoa)


class PaginaInicialTest(BaseDeIntegracao):
    """GET / — a vitrine publica."""

    def test_visitante_anonimo_recebe_a_pagina_publica(self):
        # Caminho feliz. Confere status E corpo, nao so o status.
        resposta = self.client.get(reverse('inicio'))

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'relatorios/inicio.html')
        self.assertContains(resposta, 'Elo Escolar')

    def test_quem_ja_entrou_e_levado_para_o_diario(self):
        # Caminho feliz com redirecionamento: confere o header Location.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('inicio'))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('lista_relatorios'))


class ListaRelatoriosTest(BaseDeIntegracao):
    """GET /relatorios/ — o diario de turma."""

    def setUp(self):
        super().setUp()
        self.relatorio = RelatorioDiario.objects.create(
            turma=self.turma,
            data_aula=date(2026, 11, 3),
            conteudo='Adicao com reserva',
            autor=self.professora,
        )
        self.relatorio_de_fora = RelatorioDiario.objects.create(
            turma=self.outra_turma,
            data_aula=date(2026, 11, 3),
            conteudo='Fracoes equivalentes',
            autor=self.coordenador,
        )

    def test_professora_ve_o_relatorio_da_turma_dela(self):
        # Caminho feliz: status e corpo.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('lista_relatorios'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Adicao com reserva')

    def test_professora_nao_ve_relatorio_de_turma_alheia(self):
        # A regra de visibilidade atravessando a pilha inteira ate o banco.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('lista_relatorios'))

        self.assertNotContains(resposta, 'Fracoes equivalentes')

    def test_visitante_anonimo_e_mandado_para_o_login(self):
        # Seguranca: sem sessao, nao entra. No Django a resposta e 302 para
        # a tela de login, e nao 401, porque a aplicacao e de paginas.
        resposta = self.client.get(reverse('lista_relatorios'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])


class CadastrarRelatorioTest(BaseDeIntegracao):
    """GET e POST /relatorios/novo/ — publicar o relatorio diario."""

    def dados_validos(self, **troca):
        dados = {
            'turma': self.turma.id,
            'data_aula': '2026-11-03',
            'conteudo': 'Leitura compartilhada e roda de conversa',
            'tarefa_descricao': 'Ler as paginas 20 e 21',
            'tarefa_data_entrega': '2026-11-04',
            'observacoes': '',
        }
        dados.update(troca)
        return dados

    def test_professora_abre_o_formulario(self):
        # Caminho feliz do GET.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('cadastrar_relatorio'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Conteúdo trabalhado')

    def test_professora_publica_e_o_relatorio_fica_gravado(self):
        # Caminho feliz do POST, com as tres verificacoes que o enunciado pede:
        # status, header de redirecionamento e EFEITO PERSISTIDO no banco.
        self.entrar_como(self.professora)

        resposta = self.client.post(
            reverse('cadastrar_relatorio'), self.dados_validos(),
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('lista_relatorios'))

        gravado = RelatorioDiario.objects.get(data_aula=date(2026, 11, 3))
        self.assertEqual(gravado.conteudo,
                         'Leitura compartilhada e roda de conversa')
        self.assertEqual(gravado.turma, self.turma)
        # A autoria vem da sessao, nunca do formulario.
        self.assertEqual(gravado.autor, self.professora)

    def test_responsavel_tentando_publicar_recebe_403(self):
        # Seguranca: usuario autenticado, mas sem permissao para esta acao.
        self.entrar_como(self.responsavel)

        resposta = self.client.post(
            reverse('cadastrar_relatorio'), self.dados_validos(),
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(RelatorioDiario.objects.count(), 0)

    def test_turma_de_outro_professor_e_recusada_pelo_formulario(self):
        # Cenario de erro: mesmo forjando o id de uma turma que a professora
        # nao enxerga, o formulario recusa, porque o queryset foi restrito.
        self.entrar_como(self.professora)

        resposta = self.client.post(
            reverse('cadastrar_relatorio'),
            self.dados_validos(turma=self.outra_turma.id),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Faça uma escolha válida')
        self.assertEqual(RelatorioDiario.objects.count(), 0)

    def test_formulario_sem_conteudo_nao_grava_nada(self):
        # Cenario de erro: campo obrigatorio vazio.
        self.entrar_como(self.professora)

        resposta = self.client.post(
            reverse('cadastrar_relatorio'), self.dados_validos(conteudo=''),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(RelatorioDiario.objects.count(), 0)

    def test_visitante_anonimo_nao_abre_o_formulario(self):
        # Seguranca: terceiro caso do trio exigido pelo enunciado.
        resposta = self.client.get(reverse('cadastrar_relatorio'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])
