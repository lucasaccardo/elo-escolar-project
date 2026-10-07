"""Testes unitarios do servico que grava o log de auditoria.

O log e prova: se ele gravar errado, a prova nao vale. Por isso as regras
desta funcao merecem teste. Como sempre, SimpleTestCase proibe o banco e a
classe Evento e substituida por um duble.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from auditoria.models import Evento
from auditoria.services import registrar


class RegistrarEventoTest(SimpleTestCase):
    """Regras do unico ponto do sistema que escreve no log."""

    @patch('auditoria.services.Evento')
    def test_grava_o_evento_com_os_dados_recebidos(self, evento_falso):
        # Caminho feliz, e tambem teste de interacao: confiro que a gravacao
        # foi pedida uma unica vez e com exatamente os dados informados.
        usuario = SimpleNamespace(is_authenticated=True)

        registrar(
            Evento.Acao.RELATORIO_PUBLICADO,
            usuario=usuario,
            detalhe='Turma 3A - aula de 06/10/2026',
        )

        evento_falso.objects.create.assert_called_once_with(
            acao=Evento.Acao.RELATORIO_PUBLICADO,
            usuario=usuario,
            usuario_informado='',
            detalhe='Turma 3A - aula de 06/10/2026',
        )

    @patch('auditoria.services.Evento')
    def test_visitante_nao_logado_e_gravado_como_usuario_nulo(self, evento_falso):
        # Violacao de regra: numa tentativa de login que falha, o objeto que
        # chega e um usuario anonimo. Ele nao pode ser gravado como se fosse
        # uma conta, senao o log passaria a apontar para alguem que nao e.
        anonimo = SimpleNamespace(is_authenticated=False)

        registrar(
            Evento.Acao.LOGIN_FALHA,
            usuario=anonimo,
            usuario_informado='pai@exemplo.com',
        )

        gravado = evento_falso.objects.create.call_args.kwargs
        self.assertIsNone(gravado['usuario'])
        self.assertEqual(gravado['usuario_informado'], 'pai@exemplo.com')

    @patch('auditoria.services.Evento')
    def test_texto_longo_demais_e_cortado_no_tamanho_da_coluna(self, evento_falso):
        # Caso-limite, em teste parametrizado. A coluna detalhe aguenta 255
        # caracteres. Percorro a fronteira: abaixo, exatamente em cima e
        # acima dela. Sem esse corte, um texto grande derrubaria a gravacao
        # do log bem na hora em que o log e mais necessario.
        casos = [
            (254, 254),
            (255, 255),
            (256, 255),
            (1000, 255),
        ]

        for tamanho_enviado, tamanho_esperado in casos:
            with self.subTest(tamanho=tamanho_enviado):
                evento_falso.objects.create.reset_mock()

                registrar(Evento.Acao.EMAIL, detalhe='x' * tamanho_enviado)

                gravado = evento_falso.objects.create.call_args.kwargs['detalhe']
                self.assertEqual(len(gravado), tamanho_esperado)
