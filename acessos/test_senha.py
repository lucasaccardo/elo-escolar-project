"""Testes da recuperação de senha (RF13).

O mecanismo é o do próprio Django, então o que estes testes verificam não é
a criptografia do token, e sim as decisões do projeto: que a tela não revela
quais contas existem, que a ligação é de uso único, que a troca realmente
passa a valer no login e que tudo fica registrado na auditoria.
"""

import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import SimpleTestCase, TestCase, tag
from django.urls import reverse

from acessos.emails import BrevoEmailBackend
from acessos.models import VERSAO_TERMOS, AceiteTermos
from auditoria.models import Evento
from relatorios.models import Perfil

User = get_user_model()

SENHA_ANTIGA = 'senha-antiga-123'
SENHA_NOVA = 'Senha-Nova-2026!'


class BackendDeEmailTest(SimpleTestCase):
    """Teste unitário: o backend encaixa a API no lugar do SMTP."""

    @patch('acessos.emails.enviar_email', return_value=(True, 'HTTP 201'))
    def test_cada_destinatario_vira_uma_chamada_a_api(self, api_falsa):
        backend = BrevoEmailBackend()
        mensagem = mail.EmailMessage(
            subject='Assunto', body='Corpo', to=['ana@example.com'],
        )

        enviadas = backend.send_messages([mensagem])

        self.assertEqual(enviadas, 1)
        api_falsa.assert_called_once()
        self.assertEqual(api_falsa.call_args.args[0], 'ana@example.com')

    @patch('acessos.emails.enviar_email', return_value=(False, 'sem conexao'))
    def test_falha_silenciosa_nao_derruba_a_operacao(self, _api):
        # É o mesmo tratamento do RF04: o serviço externo pode cair sem
        # desfazer o que já foi feito.
        backend = BrevoEmailBackend(fail_silently=True)
        mensagem = mail.EmailMessage(to=['ana@example.com'])

        self.assertEqual(backend.send_messages([mensagem]), 0)

    def test_lista_vazia_nao_chama_a_api(self):
        self.assertEqual(BrevoEmailBackend().send_messages([]), 0)


# A etiqueta vale também para as classes que herdam desta.
@tag('integracao')
class RecuperacaoDeSenhaTest(TestCase):

    def setUp(self):
        self.pessoa = User.objects.create_user(
            username='ana.souza',
            email='ana.souza@example.com',
            password=SENHA_ANTIGA,
            first_name='Ana',
            last_name='Souza',
        )
        Perfil.objects.create(
            usuario=self.pessoa, tipo=Perfil.Tipo.RESPONSAVEL,
        )
        AceiteTermos.objects.create(
            usuario=self.pessoa, versao=VERSAO_TERMOS,
        )

    def pedir(self, email):
        return self.client.post(reverse('password_reset'), {'email': email})

    def ligacao_do_email(self):
        """Extrai do corpo da mensagem o endereço de uso único."""
        corpo = mail.outbox[0].body
        achado = re.search(r'(/contas/reset/[^/]+/[^/\s]+/)', corpo)
        self.assertIsNotNone(achado, 'a ligação não saiu no e-mail')
        return achado.group(1)

    def test_a_tela_de_pedido_abre_sem_conta(self):
        # Caminho feliz: status e corpo. A tela precisa ser pública, senão
        # quem esqueceu a senha não chega nela.
        resposta = self.client.get(reverse('password_reset'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'E-mail cadastrado')

    def test_a_tela_de_entrada_oferece_o_caminho(self):
        resposta = self.client.get(reverse('login'))

        self.assertContains(resposta, 'Esqueci minha senha')
        self.assertContains(resposta, reverse('password_reset'))

    def test_pedido_com_email_cadastrado_envia_a_ligacao(self):
        resposta = self.pedir('ana.souza@example.com')

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/contas/reset/', mail.outbox[0].body)

    def test_pedido_com_email_inexistente_responde_igual(self):
        # Segurança: se a resposta mudasse, a tela viraria uma forma de
        # descobrir quais endereços têm conta na escola. Nada é enviado,
        # mas quem olha de fora não percebe diferença.
        resposta = self.pedir('nao.existe@example.com')

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_a_tela_seguinte_nao_confirma_se_a_conta_existe(self):
        resposta = self.client.get(reverse('password_reset_done'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Se houver uma conta')

    def test_fluxo_completo_troca_a_senha_de_verdade(self):
        # O teste que importa: ao fim, a senha nova entra e a antiga não.
        self.pedir('ana.souza@example.com')
        ligacao = self.ligacao_do_email()

        # O Django redireciona para um endereço com token mascarado antes
        # de mostrar o formulário; seguir o redirecionamento é parte do
        # mecanismo de uso único.
        abertura = self.client.get(ligacao, follow=True)
        self.assertContains(abertura, 'Criar senha nova')

        conclusao = self.client.post(
            abertura.redirect_chain[-1][0],
            {'new_password1': SENHA_NOVA, 'new_password2': SENHA_NOVA},
        )
        self.assertEqual(conclusao.status_code, 302)

        self.pessoa.refresh_from_db()
        self.assertTrue(self.pessoa.check_password(SENHA_NOVA))
        self.assertFalse(self.pessoa.check_password(SENHA_ANTIGA))

    def test_a_ligacao_so_vale_uma_vez(self):
        # Segurança: depois de usada, a mesma ligação não serve de novo.
        self.pedir('ana.souza@example.com')
        ligacao = self.ligacao_do_email()
        abertura = self.client.get(ligacao, follow=True)
        self.client.post(
            abertura.redirect_chain[-1][0],
            {'new_password1': SENHA_NOVA, 'new_password2': SENHA_NOVA},
        )

        segunda = self.client.get(ligacao, follow=True)

        self.assertContains(segunda, 'Ligação inválida')

    def test_ligacao_adulterada_e_recusada(self):
        # Cenário de erro: token trocado na mão.
        resposta = self.client.get(
            reverse('password_reset_confirm',
                    args=['MQ', 'inventado-aaaaaaaa']),
            follow=True,
        )

        self.assertContains(resposta, 'Ligação inválida')

    def test_senhas_diferentes_nao_trocam_nada(self):
        # Cenário de erro: confirmação divergente.
        self.pedir('ana.souza@example.com')
        abertura = self.client.get(self.ligacao_do_email(), follow=True)

        resposta = self.client.post(
            abertura.redirect_chain[-1][0],
            {'new_password1': SENHA_NOVA, 'new_password2': 'outra-coisa-99'},
        )

        self.assertEqual(resposta.status_code, 200)
        self.pessoa.refresh_from_db()
        self.assertTrue(self.pessoa.check_password(SENHA_ANTIGA))

    def test_a_auditoria_registra_o_pedido_e_a_troca(self):
        self.pedir('ana.souza@example.com')
        abertura = self.client.get(self.ligacao_do_email(), follow=True)
        self.client.post(
            abertura.redirect_chain[-1][0],
            {'new_password1': SENHA_NOVA, 'new_password2': SENHA_NOVA},
        )

        pedido = Evento.objects.filter(
            acao=Evento.Acao.SENHA_REDEFINICAO_PEDIDA,
        )
        self.assertEqual(pedido.count(), 1)
        # Quem pede ainda não está autenticado: o endereço vai para o campo
        # de usuário informado, e não para o de usuário.
        self.assertEqual(
            pedido.first().usuario_informado, 'ana.souza@example.com',
        )
        self.assertIsNone(pedido.first().usuario)

        self.assertEqual(
            Evento.objects.filter(
                acao=Evento.Acao.SENHA_REDEFINIDA,
                usuario=self.pessoa,
            ).count(),
            1,
        )

    def test_pedido_de_endereco_inexistente_tambem_fica_registrado(self):
        # É o que permite perceber alguém varrendo endereços.
        self.pedir('nao.existe@example.com')

        self.assertEqual(
            Evento.objects.filter(
                acao=Evento.Acao.SENHA_REDEFINICAO_PEDIDA,
                usuario_informado='nao.existe@example.com',
            ).count(),
            1,
        )
