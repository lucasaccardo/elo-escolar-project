"""Testes unitarios do painel.

Aqui ficam so as regras que NAO precisam de banco: as portas de entrada que
devolvem vazio antes de qualquer consulta. As contas de verdade, que somam
dados reais, estao em test_integracao.py, porque somar exige banco.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from painel.services import indicadores
from relatorios.models import Perfil


class IndicadoresSemPerfilTest(SimpleTestCase):
    """Regra: sem perfil ou sem conta ativa, o painel nao calcula nada."""

    def test_usuario_sem_perfil_recebe_lista_vazia(self):
        # "Negue por padrao" aplicado a numero: quem nao tem perfil nao
        # recebe indicador nenhum, nem zerado. E importante que a funcao
        # saia ANTES de consultar o banco.
        usuario = SimpleNamespace(is_active=True)  # repare: sem perfil

        self.assertEqual(indicadores(usuario), [])

    def test_conta_desativada_recebe_lista_vazia(self):
        # Caso-limite: o perfil esta certo, o que muda e so o is_active.
        usuario = SimpleNamespace(
            is_active=False,
            perfil=SimpleNamespace(tipo=Perfil.Tipo.COORDENADOR),
        )

        self.assertEqual(indicadores(usuario), [])
