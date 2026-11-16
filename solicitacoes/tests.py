"""Testes unitarios das regras de permissao das solicitacoes.

Mesmo padrao do resto do projeto: SimpleTestCase, que PROIBE o banco, e
dubles no lugar das consultas.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from relatorios.models import Perfil
from solicitacoes.models import Solicitacao
from solicitacoes.permissions import (
    pode_abrir_solicitacao,
    pode_encerrar,
    pode_responder_solicitacoes,
    solicitacoes_visiveis,
)


def usuario_com_perfil(tipo, ativo=True, identificador=1):
    return SimpleNamespace(
        id=identificador,
        is_active=ativo,
        perfil=SimpleNamespace(tipo=tipo),
    )


def solicitacao_de(autor_id, situacao=Solicitacao.Situacao.ABERTA):
    return SimpleNamespace(autor_id=autor_id, situacao=situacao)


class PodeAbrirSolicitacaoTest(SimpleTestCase):
    """Regra: a solicitacao vai da familia para a escola, nunca o inverso."""

    def test_responsavel_pode_abrir(self):
        # Caminho feliz.
        self.assertTrue(
            pode_abrir_solicitacao(
                usuario_com_perfil(Perfil.Tipo.RESPONSAVEL))
        )

    def test_professor_nao_abre_solicitacao(self):
        # A equipe tem o relatorio e o mural para falar com a familia; a
        # solicitacao existe para o caminho contrario.
        self.assertFalse(
            pode_abrir_solicitacao(usuario_com_perfil(Perfil.Tipo.PROFESSOR))
        )

    def test_responsavel_desativado_nao_abre(self):
        # Caso-limite: muda so o is_active.
        self.assertFalse(
            pode_abrir_solicitacao(
                usuario_com_perfil(Perfil.Tipo.RESPONSAVEL, ativo=False))
        )

    def test_usuario_sem_perfil_nao_abre(self):
        # "Negue por padrao".
        self.assertFalse(
            pode_abrir_solicitacao(SimpleNamespace(id=1, is_active=True))
        )


class PodeResponderSolicitacoesTest(SimpleTestCase):
    """Regra: professor, coordenacao e direcao respondem."""

    def test_professor_responde(self):
        self.assertTrue(
            pode_responder_solicitacoes(
                usuario_com_perfil(Perfil.Tipo.PROFESSOR))
        )

    def test_responsavel_nao_responde(self):
        # A diferenca entre as duas permissoes num unico teste: o
        # responsavel abre, mas nao responde.
        responsavel = usuario_com_perfil(Perfil.Tipo.RESPONSAVEL)

        self.assertTrue(pode_abrir_solicitacao(responsavel))
        self.assertFalse(pode_responder_solicitacoes(responsavel))

    def test_conta_desativada_nao_responde(self):
        self.assertFalse(
            pode_responder_solicitacoes(
                usuario_com_perfil(Perfil.Tipo.COORDENADOR, ativo=False))
        )


class PodeEncerrarTest(SimpleTestCase):
    """Regra: encerra quem abriu, e so depois de ter recebido resposta."""

    def test_autor_encerra_depois_da_resposta(self):
        # Caminho feliz.
        familia = usuario_com_perfil(Perfil.Tipo.RESPONSAVEL, identificador=4)
        pedido = solicitacao_de(4, Solicitacao.Situacao.RESPONDIDA)

        self.assertTrue(pode_encerrar(familia, pedido))

    def test_autor_nao_encerra_antes_da_resposta(self):
        # Fronteira da regra: muda so a situacao. Encerrar antes esconderia
        # da escola um pedido que ela ainda nao viu.
        familia = usuario_com_perfil(Perfil.Tipo.RESPONSAVEL, identificador=4)
        pedido = solicitacao_de(4, Solicitacao.Situacao.ABERTA)

        self.assertFalse(pode_encerrar(familia, pedido))

    def test_outra_pessoa_nao_encerra_pedido_alheio(self):
        # Violacao de regra: dois responsaveis podem cuidar da mesma
        # crianca, e o pedido de um nao e do outro.
        outra = usuario_com_perfil(Perfil.Tipo.RESPONSAVEL, identificador=9)
        pedido = solicitacao_de(4, Solicitacao.Situacao.RESPONDIDA)

        self.assertFalse(pode_encerrar(outra, pedido))

    def test_pedido_ja_encerrado_nao_encerra_de_novo(self):
        familia = usuario_com_perfil(Perfil.Tipo.RESPONSAVEL, identificador=4)
        pedido = solicitacao_de(4, Solicitacao.Situacao.ENCERRADA)

        self.assertFalse(pode_encerrar(familia, pedido))


class SolicitacoesVisiveisTest(SimpleTestCase):
    """Regra: sem perfil, nao se consulta solicitacao nenhuma."""

    @patch('solicitacoes.permissions.Solicitacao')
    def test_usuario_sem_perfil_nao_consulta(self, solicitacao_falsa):
        # O mesmo raciocinio dos outros aplicativos: provar que a funcao
        # NAO foi ao banco. Um vazamento comeca com uma consulta que nao
        # deveria ter acontecido.
        usuario = SimpleNamespace(id=1, is_active=True)  # sem perfil

        solicitacoes_visiveis(usuario)

        solicitacao_falsa.objects.none.assert_called_once_with()
        solicitacao_falsa.objects.filter.assert_not_called()   # never()
        solicitacao_falsa.objects.all.assert_not_called()      # never()
