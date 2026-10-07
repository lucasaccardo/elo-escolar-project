"""Testes unitarios do controle de acesso, do cadastro e do aviso por e-mail.

Tudo aqui herda de SimpleTestCase: nenhum teste deste arquivo pode encostar
no banco de dados nem na internet. O banco e a API externa sao substituidos
por dubles (mocks).
"""

import urllib.error
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from acessos.forms import CadastroResponsavelForm
from acessos.models import VERSAO_TERMOS
from acessos.notificacoes import enviar_email
from acessos.permissions import (
    aceitou_termos,
    pode_aprovar_acessos,
    solicitacoes_que_pode_analisar,
)
from relatorios.models import Perfil


def usuario_com_perfil(tipo, ativo=True):
    """Usuario de mentira, sem banco: so tem os campos que a regra consulta."""
    return SimpleNamespace(is_active=ativo, perfil=SimpleNamespace(tipo=tipo))


class PodeAprovarAcessosTest(SimpleTestCase):
    """Regra: quem analisa pedido de acesso e professor, coordenador e diretor."""

    def test_coordenador_ativo_pode_aprovar(self):
        # Caminho feliz.
        resultado = pode_aprovar_acessos(usuario_com_perfil(Perfil.Tipo.COORDENADOR))

        self.assertTrue(resultado)

    def test_cada_tipo_de_perfil_segue_a_tabela_da_regra(self):
        # Teste parametrizado. Em vez de escrever cinco testes quase iguais,
        # percorro a tabela da regra inteira. O subTest faz com que, se um
        # caso falhar, o relatorio diga qual perfil falhou, e os outros
        # continuem sendo verificados.
        casos = [
            (Perfil.Tipo.DIRETOR, True),
            (Perfil.Tipo.COORDENADOR, True),
            (Perfil.Tipo.PROFESSOR, True),
            (Perfil.Tipo.RESPONSAVEL, False),
            (Perfil.Tipo.ESCOLA, False),
        ]

        for tipo, esperado in casos:
            with self.subTest(perfil=tipo):
                resultado = pode_aprovar_acessos(usuario_com_perfil(tipo))

                self.assertEqual(resultado, esperado)

    def test_coordenador_com_conta_desativada_nao_pode_aprovar(self):
        # Caso-limite: o perfil continua autorizado, so a conta foi desligada.
        usuario = usuario_com_perfil(Perfil.Tipo.COORDENADOR, ativo=False)

        resultado = pode_aprovar_acessos(usuario)

        self.assertFalse(resultado)

    @patch('acessos.permissions.SolicitacaoAcesso')
    def test_quem_nao_aprova_nao_consulta_a_fila_de_pedidos(self, solicitacao_falsa):
        # Violacao de regra com never(): o responsavel nao pode nem chegar a
        # fazer a consulta. Se a consulta acontecesse, os dados ja teriam
        # saido do banco antes de alguem conferir a permissao.
        usuario = usuario_com_perfil(Perfil.Tipo.RESPONSAVEL)

        solicitacoes_que_pode_analisar(usuario)

        solicitacao_falsa.objects.none.assert_called_once_with()
        solicitacao_falsa.objects.filter.assert_not_called()  # never()


class AceitouTermosTest(SimpleTestCase):
    """Regra: vale o aceite da versao vigente dos Termos, nao de qualquer uma."""

    @patch('acessos.permissions.AceiteTermos')
    def test_aceite_da_versao_vigente_libera_o_acesso(self, aceite_falso):
        # Caminho feliz: existe registro da versao em vigor.
        aceite_falso.objects.filter.return_value.exists.return_value = True
        usuario = SimpleNamespace(pk=1)

        resultado = aceitou_termos(usuario)

        self.assertTrue(resultado)
        aceite_falso.objects.filter.assert_called_once_with(
            usuario=usuario, versao=VERSAO_TERMOS,
        )

    @patch('acessos.permissions.AceiteTermos')
    def test_sem_registro_de_aceite_o_acesso_e_negado(self, aceite_falso):
        # Violacao de regra: sem registro, nega. "Negue por padrao."
        aceite_falso.objects.filter.return_value.exists.return_value = False

        resultado = aceitou_termos(SimpleNamespace(pk=1))

        self.assertFalse(resultado)

    @patch('acessos.permissions.AceiteTermos')
    def test_a_consulta_usa_a_versao_vigente_e_nao_outra(self, aceite_falso):
        # Caso-limite: o aceite de uma versao antiga nao pode valer pela nova.
        # Provo isso mostrando que a versao procurada e a vigente.
        aceite_falso.objects.filter.return_value.exists.return_value = False
        usuario = SimpleNamespace(pk=1)

        aceitou_termos(usuario)

        versao_procurada = aceite_falso.objects.filter.call_args.kwargs['versao']
        self.assertEqual(versao_procurada, VERSAO_TERMOS)
        self.assertNotEqual(versao_procurada, '2020-01-01')


class CadastroResponsavelFormTest(SimpleTestCase):
    """Regras de validacao do cadastro publico do responsavel."""

    def _formulario_com(self, **dados):
        # Chamo os metodos clean_* direto, um de cada vez, que e o jeito
        # unitario de testar validacao: uma regra por teste.
        formulario = CadastroResponsavelForm()
        formulario.cleaned_data = dados
        return formulario

    @patch('acessos.forms.User')
    def test_email_ja_cadastrado_bloqueia_o_cadastro(self, user_falso):
        # Violacao de regra, com conferencia do TIPO e da MENSAGEM do erro.
        user_falso.objects.filter.return_value.exists.return_value = True
        formulario = self._formulario_com(email='pai@exemplo.com')

        with self.assertRaises(ValidationError) as erro:
            formulario.clean_email()

        self.assertIn('Este e-mail já está cadastrado.', erro.exception.messages)

    @patch('acessos.forms.Aluno')
    def test_rgm_inexistente_bloqueia_o_cadastro(self, aluno_falso):
        # Violacao de regra, com conferencia do TIPO e da MENSAGEM do erro.
        # Ensino o duble a estourar o mesmo erro que o banco estouraria.
        from relatorios.models import Aluno as AlunoReal
        aluno_falso.DoesNotExist = AlunoReal.DoesNotExist
        aluno_falso.objects.get.side_effect = AlunoReal.DoesNotExist
        formulario = self._formulario_com(rgm='000000')

        with self.assertRaises(ValidationError) as erro:
            formulario.clean_rgm()

        self.assertIn(
            'RGM não encontrado. Confira o número com a secretaria.',
            erro.exception.messages,
        )

    @patch('acessos.forms.User')
    def test_email_novo_e_guardado_em_minusculas(self, user_falso):
        # Caminho feliz: o e-mail vira o nome de usuario, entao e padronizado
        # em minusculas para que Pai@ e pai@ nao virem duas contas.
        user_falso.objects.filter.return_value.exists.return_value = False
        formulario = self._formulario_com(email='Pai@Exemplo.COM')

        resultado = formulario.clean_email()

        self.assertEqual(resultado, 'pai@exemplo.com')

    @patch('acessos.forms.Aluno')
    def test_rgm_digitado_com_espacos_e_limpo_antes_da_busca(self, aluno_falso):
        # Caso-limite: no celular e facil sobrar espaco antes ou depois.
        # O espaco nao pode transformar um RGM valido em "nao encontrado".
        aluno_falso.objects.get.return_value = SimpleNamespace(pk=7)
        formulario = self._formulario_com(rgm='  2024001  ')

        resultado = formulario.clean_rgm()

        self.assertEqual(resultado, '2024001')
        aluno_falso.objects.get.assert_called_once_with(rgm='2024001')


class EnviarEmailTest(SimpleTestCase):
    """Regras do aviso por e-mail, que usa uma API externa."""

    def _config_falsa(self, chave='chave-de-teste', remetente='naoresponda@exemplo.com'):
        valores = {'BREVO_API_KEY': chave, 'EMAIL_REMETENTE': remetente}
        return lambda nome, default='': valores.get(nome, default)

    @patch('acessos.notificacoes.urllib.request.urlopen')
    @patch('acessos.notificacoes.config')
    def test_envio_bem_sucedido_devolve_o_status_da_api(self, config_falso, urlopen_falso):
        # Caminho feliz. Repare que nenhum e-mail sai de verdade: a chamada
        # de rede foi trocada por um duble. Teste unitario nao usa internet.
        config_falso.side_effect = self._config_falsa()
        urlopen_falso.return_value.__enter__.return_value.status = 201

        deu_certo, detalhe = enviar_email(
            'mae@exemplo.com', 'Mae', 'Pedido aprovado', 'Seu acesso foi liberado.',
        )

        self.assertTrue(deu_certo)
        self.assertEqual(detalhe, 'HTTP 201')
        urlopen_falso.assert_called_once()

    @patch('acessos.notificacoes.urllib.request.urlopen')
    @patch('acessos.notificacoes.config')
    def test_sem_chave_configurada_a_api_nem_e_chamada(self, config_falso, urlopen_falso):
        # Violacao de regra com never(): sem credencial, a funcao desiste
        # antes de abrir conexao. Isso evita que a chave vazie numa
        # requisicao malformada e evita prender o usuario esperando a rede.
        config_falso.side_effect = self._config_falsa(chave='')

        deu_certo, detalhe = enviar_email('mae@exemplo.com', 'Mae', 'Assunto', 'Texto')

        self.assertFalse(deu_certo)
        self.assertEqual(detalhe, 'servico de e-mail nao configurado')
        urlopen_falso.assert_not_called()  # never()

    @patch('acessos.notificacoes.urllib.request.urlopen')
    @patch('acessos.notificacoes.config')
    def test_erro_da_api_vira_resposta_tratada_e_nao_quebra_o_sistema(
            self, config_falso, urlopen_falso):
        # Caso-limite: a API respondeu, mas respondeu erro. A decisao da
        # escola ja foi gravada no banco, entao a falha do e-mail nao pode
        # derrubar a tela: ela vira um retorno tratado.
        config_falso.side_effect = self._config_falsa()
        urlopen_falso.side_effect = urllib.error.HTTPError(
            'https://api.brevo.com/v3/smtp/email', 400, 'Bad Request', None, None,
        )

        deu_certo, detalhe = enviar_email('mae@exemplo.com', 'Mae', 'Assunto', 'Texto')

        self.assertFalse(deu_certo)
        self.assertEqual(detalhe, 'HTTP 400')
