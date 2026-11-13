"""Testes de INTEGRACAO do painel (RF12).

O painel nao grava nada: ele soma. Entao o que estes testes provam e que a
soma esta certa e que cada perfil soma apenas o que pode enxergar - um
numero errado aqui seria vazamento de dado, nao so erro de conta.
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from django.urls import reverse

from acessos.models import VERSAO_TERMOS, AceiteTermos
from painel.services import (
    indicadores,
    relatorios_por_semana,
    relatorios_por_turma,
)
from recados.models import Recado
from relatorios.models import Aluno, Perfil, RelatorioDiario, Turma

User = get_user_model()


# A etiqueta vale tambem para as classes que herdam desta: no Django, a
# marcacao e herdada pelas subclasses. Por isso basta etiquetar a base.
@tag('integracao')
class BaseDoPainel(TestCase):

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
        self.hoje = date.today()

    def _criar(self, usuario, tipo):
        pessoa = User.objects.create_user(
            username=usuario,
            email=f'{usuario}@example.com',
            password='senha-de-teste-123',
            first_name=usuario.split('.')[0].capitalize(),
            last_name='Teste',
        )
        Perfil.objects.create(usuario=pessoa, tipo=tipo)
        AceiteTermos.objects.create(usuario=pessoa, versao=VERSAO_TERMOS)
        return pessoa

    def entrar_como(self, pessoa):
        self.client.force_login(pessoa)

    def relatorio(self, dias_atras, turma=None, excluido=False,
                  tarefa_em=None):
        return RelatorioDiario.objects.create(
            turma=turma or self.turma,
            data_aula=self.hoje - timedelta(days=dias_atras),
            conteudo=f'Aula de {dias_atras} dias atras',
            tarefa_descricao='Exercicio' if tarefa_em is not None else '',
            tarefa_data_entrega=(
                self.hoje + timedelta(days=tarefa_em)
                if tarefa_em is not None else None
            ),
            autor=self.professora,
            excluido=excluido,
        )

    def valor_de(self, lista, pedaco_do_rotulo):
        for item in lista:
            if pedaco_do_rotulo in item['rotulo']:
                return item['valor']
        raise AssertionError(f'indicador "{pedaco_do_rotulo}" nao existe')


class TelaDoPainelTest(BaseDoPainel):

    def test_professora_abre_o_painel(self):
        # Caminho feliz: status, template e corpo.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('painel'))

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'painel/painel.html')
        self.assertContains(resposta, 'Relatórios nos últimos 30 dias')

    def test_visitante_anonimo_e_mandado_para_o_login(self):
        # Seguranca: o painel mostra numero de dado real, nao e tela publica.
        resposta = self.client.get(reverse('painel'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])

    def test_quem_entra_no_endereco_raiz_vai_para_o_painel(self):
        # O painel virou a primeira tela de quem ja tem sessao.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('inicio'))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('painel'))

    def test_a_pagina_serve_o_chartjs_do_proprio_sistema(self):
        # Decisao de projeto conferida por teste: nada de CDN. Se um dia
        # alguem trocar por um link externo, este teste reprova.
        self.relatorio(dias_atras=1)
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('painel'))

        self.assertContains(resposta, 'js/chart.umd.js')
        self.assertNotContains(resposta, 'cdn.')
        self.assertContains(resposta, 'grafico-semanas')


class IndicadoresDaEscolaTest(BaseDoPainel):

    def test_conta_os_relatorios_dos_ultimos_30_dias(self):
        self.relatorio(dias_atras=1)
        self.relatorio(dias_atras=10)
        self.relatorio(dias_atras=40)   # fora da janela

        numeros = indicadores(self.professora)

        self.assertEqual(self.valor_de(numeros, 'últimos 30 dias'), 2)

    def test_relatorio_excluido_nao_entra_na_conta(self):
        # A exclusao logica do RF11 precisa valer tambem para o painel. Se
        # nao valesse, o numero contradiria a tela.
        self.relatorio(dias_atras=1)
        self.relatorio(dias_atras=2, excluido=True)

        numeros = indicadores(self.professora)

        self.assertEqual(self.valor_de(numeros, 'últimos 30 dias'), 1)

    def test_professora_nao_conta_relatorio_de_turma_alheia(self):
        # Seguranca: o painel reaproveita turmas_visiveis, entao a regra de
        # visibilidade vale igual aqui e na lista.
        self.relatorio(dias_atras=1)
        self.relatorio(dias_atras=1, turma=self.outra_turma)

        self.assertEqual(
            self.valor_de(indicadores(self.professora), 'últimos 30 dias'), 1,
        )
        # O coordenador enxerga as duas turmas, entao conta os dois.
        self.assertEqual(
            self.valor_de(indicadores(self.coordenador), 'últimos 30 dias'), 2,
        )

    def test_conta_apenas_os_recados_dentro_do_prazo(self):
        Recado.objects.create(
            turma=self.turma, titulo='No ar', mensagem='x',
            exibir_ate=self.hoje + timedelta(days=3), autor=self.professora,
        )
        Recado.objects.create(
            turma=self.turma, titulo='Sem prazo', mensagem='x',
            exibir_ate=None, autor=self.professora,
        )
        Recado.objects.create(
            turma=self.turma, titulo='Vencido', mensagem='x',
            exibir_ate=self.hoje - timedelta(days=1), autor=self.professora,
        )

        numeros = indicadores(self.professora)

        self.assertEqual(self.valor_de(numeros, 'Recados no mural'), 2)

    def test_a_escola_ve_o_indicador_de_pedidos_pendentes(self):
        numeros = indicadores(self.coordenador)

        self.assertEqual(self.valor_de(numeros, 'Pedidos de acesso'), 0)


class IndicadoresDaFamiliaTest(BaseDoPainel):

    def test_a_familia_ve_indicadores_diferentes(self):
        # A decisao de projeto mais visivel do RF12: o painel muda conforme
        # o perfil. A familia quer saber o que precisa fazer.
        rotulos = [item['rotulo'] for item in indicadores(self.responsavel)]

        self.assertIn('Tarefas desta semana', rotulos)
        self.assertIn('Estudantes acompanhados', rotulos)
        self.assertNotIn('Pedidos de acesso pendentes', rotulos)

    def test_conta_as_tarefas_com_entrega_nos_proximos_sete_dias(self):
        self.relatorio(dias_atras=1, tarefa_em=2)    # entra
        self.relatorio(dias_atras=2, tarefa_em=7)    # fronteira: entra
        self.relatorio(dias_atras=3, tarefa_em=9)    # fora da janela
        self.relatorio(dias_atras=4, tarefa_em=-1)   # ja venceu
        self.relatorio(dias_atras=5)                 # sem tarefa

        numeros = indicadores(self.responsavel)

        self.assertEqual(self.valor_de(numeros, 'Tarefas desta semana'), 2)

    def test_conta_os_estudantes_vinculados(self):
        numeros = indicadores(self.responsavel)

        self.assertEqual(self.valor_de(numeros, 'Estudantes acompanhados'), 1)


class GraficosTest(BaseDoPainel):

    def test_grafico_de_barras_agrupa_por_turma(self):
        self.relatorio(dias_atras=1)
        self.relatorio(dias_atras=2)
        self.relatorio(dias_atras=3, turma=self.outra_turma)

        dados = relatorios_por_turma(self.coordenador)

        self.assertEqual(dados['rotulos'], ['3 ANO C', '5 ANO A'])
        self.assertEqual(dados['valores'], [2, 1])

    def test_grafico_de_barras_vem_vazio_quando_nao_ha_relatorio(self):
        dados = relatorios_por_turma(self.coordenador)

        self.assertEqual(dados['rotulos'], [])
        self.assertEqual(dados['valores'], [])

    def test_grafico_de_linha_traz_sempre_oito_semanas(self):
        # Semana sem publicacao precisa aparecer como zero. Se as semanas
        # vazias sumissem, o grafico mentiria: o periodo pareceria continuo.
        self.relatorio(dias_atras=0)

        dados = relatorios_por_semana(self.professora)

        self.assertEqual(len(dados['rotulos']), 8)
        self.assertEqual(len(dados['valores']), 8)
        self.assertEqual(sum(dados['valores']), 1)
        self.assertIn(0, dados['valores'])
