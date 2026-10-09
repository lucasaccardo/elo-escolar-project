"""Testes unitarios das regras de permissao dos relatorios.

Unitario quer dizer: testa UMA regra de cada vez, sem banco, sem rede e sem
servidor. Por isso herdamos de SimpleTestCase, que e a classe do Django que
PROIBE o teste de encostar no banco de dados. Se algum teste daqui tentar
consultar o banco, o proprio Django reprova o teste.

As consultas ao banco que as funcoes fazem sao substituidas por dubles
(mocks), criados com unittest.mock.patch.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from relatorios.models import Perfil
from relatorios.permissions import pode_publicar_relatorio, turmas_visiveis


def usuario_com_perfil(tipo, ativo=True):
    """Monta um usuario de mentira, sem gravar nada no banco.

    SimpleNamespace e um objeto simples do Python: o que eu escrevo aqui
    vira atributo dele. Para a funcao testada isso basta, porque ela so
    consulta user.is_active e user.perfil.tipo.
    """
    return SimpleNamespace(is_active=ativo, perfil=SimpleNamespace(tipo=tipo))


class PodePublicarRelatorioTest(SimpleTestCase):
    """Regra: so professor, coordenador e diretor ativos publicam relatorio."""

    def test_professor_ativo_pode_publicar(self):
        # Caminho feliz: e o uso normal, aquele que tem de funcionar sempre.
        # Arrange
        usuario = usuario_com_perfil(Perfil.Tipo.PROFESSOR)

        # Act
        resultado = pode_publicar_relatorio(usuario)

        # Assert
        self.assertTrue(resultado)

    def test_responsavel_nao_pode_publicar(self):
        # Violacao de regra: o responsavel le relatorio, nunca publica.
        usuario = usuario_com_perfil(Perfil.Tipo.RESPONSAVEL)

        resultado = pode_publicar_relatorio(usuario)

        self.assertFalse(resultado)

    def test_professor_com_conta_desativada_nao_pode_publicar(self):
        # Caso-limite: o perfil esta certo, o que muda e so o is_active.
        # E a fronteira da regra: um unico campo decide o sim e o nao.
        usuario = usuario_com_perfil(Perfil.Tipo.PROFESSOR, ativo=False)

        resultado = pode_publicar_relatorio(usuario)

        self.assertFalse(resultado)

    def test_usuario_sem_perfil_nao_pode_publicar(self):
        # Violacao de regra: "negue por padrao". Quem nao tem perfil nao
        # recebe permissao nenhuma, mesmo com a conta ativa.
        usuario = SimpleNamespace(is_active=True)  # repare: sem perfil

        resultado = pode_publicar_relatorio(usuario)

        self.assertFalse(resultado)


class TurmasVisiveisTest(SimpleTestCase):
    """Regra: cada perfil enxerga um conjunto diferente de turmas."""

    @patch('relatorios.permissions.Turma')
    def test_professor_so_enxerga_as_turmas_dele(self, turma_falsa):
        # Teste de interacao: aqui nao interessa QUAL lista volta, e sim
        # que a funcao pediu ao banco exatamente o filtro certo. O decorador
        # @patch troca a classe Turma por um duble so dentro deste teste.
        usuario = usuario_com_perfil(Perfil.Tipo.PROFESSOR)

        turmas_visiveis(usuario)

        # Equivale ao verify(...) do Mockito: confere a chamada e o argumento.
        turma_falsa.objects.filter.assert_called_once_with(professor=usuario)

    @patch('relatorios.permissions.Turma')
    def test_usuario_sem_perfil_nao_consulta_turma_nenhuma(self, turma_falsa):
        # Violacao de regra com never(): o importante aqui e provar que a
        # funcao NAO foi ao banco buscar todas as turmas. Um vazamento de
        # dados comeca exatamente assim, com uma consulta que nao devia
        # ter acontecido.
        usuario = SimpleNamespace(is_active=True)  # sem perfil

        turmas_visiveis(usuario)

        turma_falsa.objects.none.assert_called_once_with()
        turma_falsa.objects.all.assert_not_called()      # never()
        turma_falsa.objects.filter.assert_not_called()   # never()
