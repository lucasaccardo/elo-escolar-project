"""Testes da confirmação de e-mail no cadastro (RF14).

O que está sendo verificado aqui não é "o código chegou", e sim as decisões
do projeto: que o código não fica legível no banco, que ele vence, que não se
pode ficar adivinhando à vontade, que a fila da escola só recebe pedido com
endereço provado e que a identidade de quem confirma vem da sessão — e não de
um número na barra de endereços, que qualquer um poderia trocar.
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from django.urls import reverse
from django.utils import timezone

from acessos.models import (
    MAXIMO_DE_TENTATIVAS,
    VALIDADE_DO_CODIGO_MINUTOS,
    ConfirmacaoEmail,
)
from auditoria.models import Evento
from relatorios.models import Aluno, Perfil, Turma

User = get_user_model()


class CodigoDeConfirmacaoTest(TestCase):
    """Testes da regra, chamando o modelo direto, sem passar por tela."""

    def setUp(self):
        self.pessoa = User.objects.create_user(
            username='ana.souza@example.com',
            email='ana.souza@example.com',
            password='SenhaForte2026',
            first_name='Ana',
            last_name='Souza',
            is_active=False,
        )

    def test_o_codigo_tem_seis_digitos(self):
        _, codigo = ConfirmacaoEmail.gerar(self.pessoa)

        self.assertEqual(len(codigo), 6)
        self.assertTrue(codigo.isdigit())

    def test_o_codigo_nao_fica_legivel_no_banco(self):
        # A mesma decisão da senha: quem consegue ler a tabela não pode usar
        # o que encontra lá. O que fica gravado é o resumo criptográfico.
        confirmacao, codigo = ConfirmacaoEmail.gerar(self.pessoa)

        self.assertNotIn(codigo, confirmacao.codigo_hash)
        self.assertNotEqual(confirmacao.codigo_hash, codigo)

    def test_codigo_certo_confirma(self):
        # Caminho feliz.
        confirmacao, codigo = ConfirmacaoEmail.gerar(self.pessoa)

        deu_certo, _ = confirmacao.conferir(codigo)

        self.assertTrue(deu_certo)
        self.assertTrue(confirmacao.confirmado)
        self.assertIsNotNone(confirmacao.confirmado_em)

    def test_codigo_errado_nao_confirma_e_conta_a_tentativa(self):
        confirmacao, codigo = ConfirmacaoEmail.gerar(self.pessoa)
        errado = '000000' if codigo != '000000' else '111111'

        deu_certo, motivo = confirmacao.conferir(errado)

        self.assertFalse(deu_certo)
        self.assertEqual(motivo, 'codigo incorreto')
        self.assertFalse(confirmacao.confirmado)
        confirmacao.refresh_from_db()
        self.assertEqual(confirmacao.tentativas, 1)

    def test_codigo_vencido_nao_serve_mesmo_estando_certo(self):
        # Fronteira da regra: muda só o relógio. Um código que valesse para
        # sempre transformaria o acesso ao e-mail de ontem em acesso de hoje.
        confirmacao, codigo = ConfirmacaoEmail.gerar(self.pessoa)
        confirmacao.expira_em = timezone.now() - timedelta(seconds=1)
        confirmacao.save(update_fields=['expira_em'])

        deu_certo, motivo = confirmacao.conferir(codigo)

        self.assertFalse(deu_certo)
        self.assertEqual(motivo, 'expirado')
        self.assertFalse(confirmacao.confirmado)

    def test_o_prazo_e_o_configurado(self):
        confirmacao, _ = ConfirmacaoEmail.gerar(self.pessoa)

        faltando = confirmacao.expira_em - timezone.now()

        self.assertLessEqual(
            faltando, timedelta(minutes=VALIDADE_DO_CODIGO_MINUTOS),
        )
        self.assertGreater(
            faltando, timedelta(minutes=VALIDADE_DO_CODIGO_MINUTOS - 1),
        )

    def test_depois_do_limite_de_tentativas_para_de_conferir(self):
        # Segurança: são um milhão de combinações. Sem limite, um programa
        # simples acerta por tentativa e erro. Com cinco, não acerta.
        confirmacao, codigo = ConfirmacaoEmail.gerar(self.pessoa)
        errado = '000000' if codigo != '000000' else '111111'
        for _ in range(MAXIMO_DE_TENTATIVAS):
            confirmacao.conferir(errado)

        # Agora nem o código certo passa: é preciso pedir outro.
        deu_certo, motivo = confirmacao.conferir(codigo)

        self.assertFalse(deu_certo)
        self.assertEqual(motivo, 'tentativas esgotadas')

    def test_pedir_outro_codigo_invalida_o_anterior(self):
        # Caso-limite: dois códigos válidos ao mesmo tempo seria dobrar a
        # chance de acerto de quem está adivinhando.
        _, primeiro = ConfirmacaoEmail.gerar(self.pessoa)
        confirmacao, segundo = ConfirmacaoEmail.gerar(self.pessoa)

        self.assertFalse(confirmacao.conferir(primeiro)[0])
        self.assertTrue(confirmacao.conferir(segundo)[0])

    def test_pedir_outro_codigo_zera_as_tentativas(self):
        confirmacao, codigo = ConfirmacaoEmail.gerar(self.pessoa)
        errado = '000000' if codigo != '000000' else '111111'
        for _ in range(MAXIMO_DE_TENTATIVAS):
            confirmacao.conferir(errado)

        confirmacao, novo = ConfirmacaoEmail.gerar(self.pessoa)

        self.assertEqual(confirmacao.tentativas, 0)
        self.assertTrue(confirmacao.conferir(novo)[0])

    def test_cada_pessoa_tem_no_maximo_uma_confirmacao(self):
        ConfirmacaoEmail.gerar(self.pessoa)
        ConfirmacaoEmail.gerar(self.pessoa)

        self.assertEqual(
            ConfirmacaoEmail.objects.filter(usuario=self.pessoa).count(), 1,
        )


# A etiqueta vale também para as classes que herdam desta.
@tag('integracao')
class TelaDeConfirmacaoTest(TestCase):
    """A requisição entrando pela URL e atravessando view, regra e banco."""

    def setUp(self):
        professora = User.objects.create_user(
            username='marcia.silva', email='marcia.silva@example.com',
            password='senha-de-teste-123', first_name='Marcia',
            last_name='Silva',
        )
        Perfil.objects.create(usuario=professora, tipo=Perfil.Tipo.PROFESSOR)
        turma = Turma.objects.create(
            nome='3 ANO C', ano_letivo=2026, professor=professora,
        )
        Aluno.objects.create(
            nome_completo='Pedro Souza', rgm='2026001', turma=turma,
        )

    def dados_do_cadastro(self, **troca):
        dados = {
            'nome': 'Ana',
            'sobrenome': 'Souza',
            'email': 'ana.souza@example.com',
            'senha': 'SenhaForte2026',
            'confirmar_senha': 'SenhaForte2026',
            'rgm': '2026001',
            'aceite_termos': 'on',
        }
        dados.update(troca)
        return dados

    def cadastrar(self):
        """Faz o cadastro e devolve o código que foi enviado por e-mail.

        O código em texto existe só dentro da chamada que o envia, então o
        teste o recolhe do dublê que está no lugar da API externa.
        """
        with patch('acessos.views.enviar_email',
                   return_value=(True, 'HTTP 201')) as email_falso:
            self.client.post(reverse('cadastro'), self.dados_do_cadastro())
        corpo = email_falso.call_args.args[3]
        codigo = ''.join(c for c in corpo.split('confirmação é: ')[1][:6])
        return User.objects.get(username='ana.souza@example.com'), codigo

    def test_o_cadastro_leva_para_a_tela_de_confirmacao(self):
        # Caminho feliz: status, destino e corpo.
        with patch('acessos.views.enviar_email',
                   return_value=(True, 'HTTP 201')):
            resposta = self.client.post(
                reverse('cadastro'), self.dados_do_cadastro(), follow=True,
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Confirme seu e-mail')
        self.assertContains(resposta, 'ana.souza@example.com')

    def test_o_cadastro_dispara_um_e_mail_com_o_codigo(self):
        _, codigo = self.cadastrar()

        self.assertEqual(len(codigo), 6)
        self.assertTrue(codigo.isdigit())

    def test_codigo_certo_confirma_e_leva_ao_pedido_enviado(self):
        # Caminho feliz com efeito persistido: a requisição HTTP grava a
        # confirmação no banco.
        pessoa, codigo = self.cadastrar()

        resposta = self.client.post(
            reverse('confirmar_email'), {'codigo': codigo},
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('cadastro_enviado'))
        self.assertTrue(pessoa.confirmacao_email.confirmado)

    def test_codigo_errado_volta_com_aviso_e_nao_confirma(self):
        # Cenário de erro.
        pessoa, codigo = self.cadastrar()
        errado = '000000' if codigo != '000000' else '111111'

        resposta = self.client.post(
            reverse('confirmar_email'), {'codigo': errado}, follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Código incorreto')
        self.assertFalse(pessoa.confirmacao_email.confirmado)

    def test_codigo_com_letras_nao_chega_a_ser_conferido(self):
        # Cenário de erro na validação do formulário, antes da regra.
        pessoa, _ = self.cadastrar()

        resposta = self.client.post(
            reverse('confirmar_email'), {'codigo': 'abcdef'},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'seis dígitos')
        pessoa.confirmacao_email.refresh_from_db()
        self.assertEqual(pessoa.confirmacao_email.tentativas, 0)

    def test_quem_nao_passou_pelo_cadastro_e_mandado_de_volta(self):
        # Segurança: a identidade de quem confirma vem da sessão. Sem ela,
        # a tela não existe — não há um número para trocar na URL e tentar
        # confirmar a conta de outra pessoa.
        resposta = self.client.get(reverse('confirmar_email'))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('cadastro'))

    def test_o_codigo_de_uma_pessoa_nao_confirma_a_conta_de_outra(self):
        # Segurança, continuação: mesmo tendo em mãos um código válido, ele
        # só vale para a sessão em que o cadastro foi feito.
        outra = User.objects.create_user(
            username='bia@example.com', email='bia@example.com',
            password='x', is_active=False,
        )
        _, codigo_da_outra = ConfirmacaoEmail.gerar(outra)
        self.cadastrar()

        self.client.post(reverse('confirmar_email'),
                         {'codigo': codigo_da_outra})

        outra.refresh_from_db()
        self.assertFalse(outra.confirmacao_email.confirmado)

    def test_pedir_outro_codigo_envia_de_novo(self):
        pessoa, primeiro = self.cadastrar()

        with patch('acessos.views.enviar_email',
                   return_value=(True, 'HTTP 201')) as email_falso:
            resposta = self.client.post(reverse('reenviar_codigo'))

        self.assertEqual(resposta.status_code, 302)
        email_falso.assert_called_once()
        # E o código antigo deixou de servir.
        self.client.post(reverse('confirmar_email'), {'codigo': primeiro})
        self.assertFalse(pessoa.confirmacao_email.confirmado)

    def test_reenviar_por_get_e_recusado_com_405(self):
        # Cenário de erro com outro status: reenviar muda estado no banco,
        # então só POST.
        self.cadastrar()

        resposta = self.client.get(reverse('reenviar_codigo'))

        self.assertEqual(resposta.status_code, 405)

    def test_a_confirmacao_fica_registrada_na_auditoria(self):
        _, codigo = self.cadastrar()

        self.client.post(reverse('confirmar_email'), {'codigo': codigo})

        self.assertEqual(
            Evento.objects.filter(
                acao=Evento.Acao.EMAIL_CONFIRMADO,
                usuario_informado='ana.souza@example.com',
            ).count(),
            1,
        )
