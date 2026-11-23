"""Testes do limite de tentativas de entrada.

O que está sendo verificado aqui não é "a senha errada é recusada" — isso o
arcabouço já faz. É a decisão do projeto de impedir a adivinhação por
tentativa e erro: depois de um número de erros, nem a senha certa entra,
pelo tempo da janela.
"""

from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, tag
from django.urls import reverse
from django.utils import timezone

from acessos.forms import origem_da_requisicao
from acessos.models import (
    JANELA_DE_BLOQUEIO_MINUTOS,
    TENTATIVAS_POR_CONTA,
    TENTATIVAS_POR_ORIGEM,
    VERSAO_TERMOS,
    AceiteTermos,
    TentativaDeLogin,
)
from auditoria.models import Evento
from relatorios.models import Perfil

User = get_user_model()

CONTA = 'marcia.silva@example.com'
SENHA = 'SenhaCerta2026!'
ORIGEM = '203.0.113.7'      # faixa reservada para documentação


class OrigemDaRequisicaoTest(SimpleTestCase):
    """Teste unitário: de onde o endereço do visitante é lido."""

    def requisicao(self, **cabecalhos):
        return SimpleNamespace(META=cabecalhos)

    def test_le_o_cabecalho_encaminhado_primeiro(self):
        # Atrás do servidor de publicação, REMOTE_ADDR é o próprio
        # servidor: todo mundo pareceria vir do mesmo lugar.
        pedido = self.requisicao(
            HTTP_X_FORWARDED_FOR='203.0.113.7, 10.0.0.1',
            REMOTE_ADDR='10.0.0.1',
        )

        self.assertEqual(origem_da_requisicao(pedido), '203.0.113.7')

    def test_sem_cabecalho_usa_o_endereco_direto(self):
        pedido = self.requisicao(REMOTE_ADDR='198.51.100.4')

        self.assertEqual(origem_da_requisicao(pedido), '198.51.100.4')

    def test_sem_requisicao_devolve_nada(self):
        # Caso-limite: formulário construído fora de uma requisição.
        self.assertIsNone(origem_da_requisicao(None))


class ContagemDeTentativasTest(TestCase):
    """Testes da regra, chamando o modelo direto, sem passar por tela."""

    def errar(self, vezes, identificador=CONTA, origem=ORIGEM):
        for _ in range(vezes):
            TentativaDeLogin.registrar_falha(identificador, origem)

    def test_abaixo_do_limite_nao_bloqueia(self):
        self.errar(TENTATIVAS_POR_CONTA - 1)

        self.assertFalse(TentativaDeLogin.bloqueado(CONTA, ORIGEM))

    def test_no_limite_bloqueia(self):
        # Fronteira da regra: muda só uma tentativa.
        self.errar(TENTATIVAS_POR_CONTA)

        self.assertTrue(TentativaDeLogin.bloqueado(CONTA, ORIGEM))

    def test_tentativa_fora_da_janela_nao_conta(self):
        # O bloqueio é temporário de propósito: fosse permanente, qualquer
        # pessoa poderia trancar a conta de outra só errando a senha.
        self.errar(TENTATIVAS_POR_CONTA)
        antiga = timezone.now() - timedelta(
            minutes=JANELA_DE_BLOQUEIO_MINUTOS + 1)
        TentativaDeLogin.objects.update(em=antiga)

        self.assertFalse(TentativaDeLogin.bloqueado(CONTA, ORIGEM))

    def test_outra_conta_na_mesma_origem_nao_e_afetada_abaixo_do_limite(self):
        # O limite por conta não pode respingar em quem divide a rede —
        # numa escola, todo mundo sai pelo mesmo endereço.
        self.errar(TENTATIVAS_POR_CONTA)

        self.assertFalse(
            TentativaDeLogin.bloqueado('outra.pessoa@example.com', ORIGEM)
        )

    def test_muitas_contas_na_mesma_origem_bloqueiam_a_origem(self):
        # Defesa secundária: varrer várias contas do mesmo lugar é o que o
        # limite por conta sozinho não pegaria.
        for i in range(TENTATIVAS_POR_ORIGEM):
            TentativaDeLogin.registrar_falha(f'pessoa{i}@example.com', ORIGEM)

        self.assertTrue(
            TentativaDeLogin.bloqueado('mais.uma@example.com', ORIGEM)
        )

    def test_sem_origem_conhecida_so_vale_o_limite_por_conta(self):
        for i in range(TENTATIVAS_POR_ORIGEM):
            TentativaDeLogin.registrar_falha(f'pessoa{i}@example.com', None)

        self.assertFalse(TentativaDeLogin.bloqueado('mais.uma@example.com',
                                                    None))

    def test_esquecer_zera_a_contagem(self):
        self.errar(TENTATIVAS_POR_CONTA)

        TentativaDeLogin.esquecer(CONTA, ORIGEM)

        self.assertFalse(TentativaDeLogin.bloqueado(CONTA, ORIGEM))

    def test_a_senha_nunca_e_gravada(self):
        # Violação que seria grave: o registro guarda o que foi digitado no
        # campo de usuário, e nada mais.
        TentativaDeLogin.registrar_falha(CONTA, ORIGEM)

        campos = {c.name for c in TentativaDeLogin._meta.get_fields()}
        self.assertEqual(campos, {'id', 'identificador', 'origem', 'em'})


# A etiqueta vale também para as classes que herdam desta.
@tag('integracao')
class BloqueioNaTelaDeEntradaTest(TestCase):
    """A requisição entrando pela URL, atravessando formulário e banco."""

    def setUp(self):
        self.pessoa = User.objects.create_user(
            username=CONTA, email=CONTA, password=SENHA,
            first_name='Márcia', last_name='Silva',
        )
        Perfil.objects.create(usuario=self.pessoa, tipo=Perfil.Tipo.PROFESSOR)
        AceiteTermos.objects.create(usuario=self.pessoa, versao=VERSAO_TERMOS)

    def tentar(self, senha, usuario=CONTA):
        return self.client.post(
            reverse('login'),
            {'username': usuario, 'password': senha},
            REMOTE_ADDR=ORIGEM,
        )

    def errar_ate_bloquear(self, usuario=CONTA):
        for _ in range(TENTATIVAS_POR_CONTA):
            self.tentar('senha-errada', usuario)

    def test_senha_certa_entra_normalmente(self):
        # Caminho feliz, para o teste seguinte significar alguma coisa.
        resposta = self.tentar(SENHA)

        self.assertEqual(resposta.status_code, 302)

    def test_depois_do_limite_nem_a_senha_certa_entra(self):
        # O teste que importa: é isto que impede a adivinhação.
        self.errar_ate_bloquear()

        resposta = self.tentar(SENHA)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Muitas tentativas seguidas')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_passada_a_janela_a_senha_certa_volta_a_entrar(self):
        self.errar_ate_bloquear()
        antiga = timezone.now() - timedelta(
            minutes=JANELA_DE_BLOQUEIO_MINUTOS + 1)
        TentativaDeLogin.objects.update(em=antiga)

        resposta = self.tentar(SENHA)

        self.assertEqual(resposta.status_code, 302)

    def test_entrar_com_sucesso_zera_a_contagem(self):
        for _ in range(TENTATIVAS_POR_CONTA - 1):
            self.tentar('senha-errada')

        self.tentar(SENHA)
        self.client.logout()
        for _ in range(TENTATIVAS_POR_CONTA - 1):
            self.tentar('senha-errada')

        # Sem o zeramento, estas seriam a sexta, sétima e oitava.
        self.assertEqual(self.tentar(SENHA).status_code, 302)

    def test_a_mensagem_nao_revela_se_a_conta_existe(self):
        # Segurança: se a resposta ao bloqueio variasse entre conta
        # existente e inexistente, a tela viraria um meio de descobrir
        # quem tem conta na escola.
        self.errar_ate_bloquear()
        existente = self.tentar(SENHA)

        self.client.post(reverse('login'),
                         {'username': 'nao.existe@example.com',
                          'password': 'x'}, REMOTE_ADDR='198.51.100.9')
        for _ in range(TENTATIVAS_POR_CONTA):
            self.client.post(reverse('login'),
                             {'username': 'nao.existe@example.com',
                              'password': 'x'}, REMOTE_ADDR='198.51.100.9')
        inexistente = self.client.post(
            reverse('login'),
            {'username': 'nao.existe@example.com', 'password': 'x'},
            REMOTE_ADDR='198.51.100.9',
        )

        self.assertContains(existente, 'Muitas tentativas seguidas')
        self.assertContains(inexistente, 'Muitas tentativas seguidas')

    def test_o_bloqueio_fica_registrado_na_auditoria(self):
        # É o que permite perceber, depois, uma tentativa de invasão.
        self.errar_ate_bloquear()

        self.tentar(SENHA)

        eventos = Evento.objects.filter(
            acao=Evento.Acao.LOGIN_BLOQUEADO, usuario_informado=CONTA,
        )
        self.assertGreaterEqual(eventos.count(), 1)
        self.assertIn(ORIGEM, eventos.first().detalhe)

    def test_a_senha_digitada_nao_vai_para_a_auditoria(self):
        # Violação que seria grave, e fácil de cometer sem querer.
        self.tentar('senha-secreta-do-usuario')

        for evento in Evento.objects.all():
            self.assertNotIn('senha-secreta-do-usuario', evento.detalhe)
            self.assertNotIn('senha-secreta-do-usuario',
                             evento.usuario_informado)
