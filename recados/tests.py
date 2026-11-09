"""Testes unitarios das regras de permissao dos recados.

Mesmo padrao dos testes de relatorios: SimpleTestCase, que PROIBE o banco, e
dubles no lugar das consultas.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from recados.permissions import (
    eh_equipe_da_escola,
    pode_publicar_recado,
    pode_publicar_recado_geral,
    recados_visiveis,
)
from relatorios.models import Perfil


def usuario_com_perfil(tipo, ativo=True):
    return SimpleNamespace(is_active=ativo, perfil=SimpleNamespace(tipo=tipo))


class PodePublicarRecadoTest(SimpleTestCase):
    """Regra: professor, coordenacao e direcao publicam recado de turma."""

    def test_professor_pode_publicar_recado(self):
        # Caminho feliz.
        self.assertTrue(
            pode_publicar_recado(usuario_com_perfil(Perfil.Tipo.PROFESSOR))
        )

    def test_responsavel_nao_publica_recado(self):
        # Violacao de regra: a familia le o mural, nao escreve nele.
        self.assertFalse(
            pode_publicar_recado(usuario_com_perfil(Perfil.Tipo.RESPONSAVEL))
        )

    def test_professor_desativado_nao_publica(self):
        # Caso-limite: muda so o is_active.
        self.assertFalse(
            pode_publicar_recado(
                usuario_com_perfil(Perfil.Tipo.PROFESSOR, ativo=False)
            )
        )

    def test_usuario_sem_perfil_nao_publica(self):
        # "Negue por padrao".
        self.assertFalse(pode_publicar_recado(SimpleNamespace(is_active=True)))


class PodePublicarRecadoGeralTest(SimpleTestCase):
    """Regra: falar em nome da ESCOLA INTEIRA e so da gestao."""

    def test_coordenador_fala_pela_escola(self):
        self.assertTrue(
            pode_publicar_recado_geral(
                usuario_com_perfil(Perfil.Tipo.COORDENADOR)
            )
        )

    def test_diretor_fala_pela_escola(self):
        self.assertTrue(
            pode_publicar_recado_geral(usuario_com_perfil(Perfil.Tipo.DIRETOR))
        )

    def test_professor_nao_fala_pela_escola(self):
        # A diferenca entre as duas permissoes, num unico teste: o professor
        # publica recado, mas nao publica recado GERAL.
        professor = usuario_com_perfil(Perfil.Tipo.PROFESSOR)

        self.assertTrue(pode_publicar_recado(professor))
        self.assertFalse(pode_publicar_recado_geral(professor))


class EhEquipeDaEscolaTest(SimpleTestCase):
    """Regra: quem enxerga tambem os recados ja encerrados."""

    def test_professor_e_equipe(self):
        self.assertTrue(
            eh_equipe_da_escola(usuario_com_perfil(Perfil.Tipo.PROFESSOR))
        )

    def test_responsavel_nao_e_equipe(self):
        self.assertFalse(
            eh_equipe_da_escola(usuario_com_perfil(Perfil.Tipo.RESPONSAVEL))
        )


class RecadosVisiveisTest(SimpleTestCase):
    """Regra: sem perfil, nao se consulta recado nenhum."""

    @patch('recados.permissions.Recado')
    def test_usuario_sem_perfil_nao_consulta_recado(self, recado_falso):
        # O mesmo raciocinio do teste de turmas_visiveis: provar que a funcao
        # NAO foi ao banco. Um vazamento comeca com uma consulta que nao
        # deveria ter acontecido.
        usuario = SimpleNamespace(is_active=True)  # sem perfil

        recados_visiveis(usuario)

        recado_falso.objects.none.assert_called_once_with()
        recado_falso.objects.filter.assert_not_called()   # never()
        recado_falso.objects.all.assert_not_called()      # never()
