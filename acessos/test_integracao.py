"""Testes de INTEGRACAO das rotas de acesso, consentimento e aprovacao.

Mesmo principio do outro arquivo: TestCase com banco de teste de verdade, a
requisicao entrando pela URL e atravessando middleware, view, regra e ORM.

A unica coisa trocada por duble e a funcao enviar_email, porque ela sai para a
internet. O enunciado manda mockar so dependencia externa — view, regra e banco
continuam reais.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from django.urls import reverse

from acessos.models import VERSAO_TERMOS, AceiteTermos, SolicitacaoAcesso
from relatorios.models import Aluno, Perfil, RelatorioDiario, Turma

User = get_user_model()


# A etiqueta vale tambem para as classes que herdam desta: no Django, a
# marcacao e herdada pelas subclasses. Por isso basta etiquetar a base.
@tag('integracao')
class BaseDeAcesso(TestCase):

    def setUp(self):
        self.professora = self._criar('marcia.silva', Perfil.Tipo.PROFESSOR)
        self.coordenador = self._criar('joao.pereira', Perfil.Tipo.COORDENADOR)

        self.turma = Turma.objects.create(
            nome='3 ANO C', ano_letivo=2026, professor=self.professora,
        )
        self.aluno = Aluno.objects.create(
            nome_completo='Pedro Souza', rgm='2026001', turma=self.turma,
        )

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


class PaginasPublicasTest(BaseDeAcesso):
    """As telas que qualquer pessoa abre, sem conta."""

    def test_termos_de_uso_abrem_para_qualquer_um(self):
        resposta = self.client.get(reverse('termos'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Termos de Uso')

    def test_politica_de_privacidade_abre_para_qualquer_um(self):
        resposta = self.client.get(reverse('privacidade'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Privacidade')

    def test_tela_de_confirmacao_do_cadastro_abre(self):
        resposta = self.client.get(reverse('cadastro_enviado'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Pedido enviado')


class CadastroResponsavelTest(BaseDeAcesso):
    """GET e POST /acessos/cadastro/ — a porta de entrada do responsavel."""

    def test_formulario_de_cadastro_abre(self):
        resposta = self.client.get(reverse('cadastro'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'RGM do aluno')

    def test_cadastro_valido_grava_conta_pedido_e_aceite(self):
        # Caminho feliz com EFEITO PERSISTIDO: uma requisicao HTTP grava em
        # tres tabelas diferentes, dentro da mesma transacao.
        resposta = self.client.post(reverse('cadastro'), self.dados_do_cadastro())

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('cadastro_enviado'))

        conta = User.objects.get(username='ana.souza@example.com')
        # A conta nasce DESLIGADA: existe, mas nao entra.
        self.assertFalse(conta.is_active)

        pedido = SolicitacaoAcesso.objects.get(usuario=conta)
        self.assertEqual(pedido.aluno, self.aluno)
        self.assertEqual(pedido.status, SolicitacaoAcesso.Status.PENDENTE)

        self.assertTrue(
            AceiteTermos.objects.filter(usuario=conta, versao=VERSAO_TERMOS).exists()
        )

    def test_rgm_inexistente_nao_cria_conta_nenhuma(self):
        # Cenario de erro. Repare que a tela nao revela nome de crianca.
        resposta = self.client.post(
            reverse('cadastro'), self.dados_do_cadastro(rgm='000000'),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'RGM não encontrado')
        self.assertFalse(User.objects.filter(username='ana.souza@example.com').exists())

    def test_email_repetido_nao_cria_segunda_conta(self):
        # Cenario de erro: o e-mail vira nome de usuario, entao nao repete.
        self.client.post(reverse('cadastro'), self.dados_do_cadastro())

        resposta = self.client.post(reverse('cadastro'), self.dados_do_cadastro())

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'já está cadastrado')
        self.assertEqual(
            User.objects.filter(username='ana.souza@example.com').count(), 1,
        )

    def test_senhas_diferentes_nao_criam_conta(self):
        # Cenario de erro na validacao cruzada entre dois campos.
        resposta = self.client.post(
            reverse('cadastro'),
            self.dados_do_cadastro(confirmar_senha='OutraCoisa2026'),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'senhas não conferem')
        self.assertFalse(User.objects.filter(username='ana.souza@example.com').exists())


class AceiteDosTermosTest(BaseDeAcesso):
    """O middleware que cobra o aceite, atravessando a aplicacao inteira."""

    def setUp(self):
        super().setUp()
        # Uma conta ligada, com perfil, mas SEM registro de aceite.
        self.sem_aceite = User.objects.create_user(
            username='carlos.lima', email='carlos.lima@example.com',
            password='senha-de-teste-123', first_name='Carlos', last_name='Lima',
        )
        Perfil.objects.create(usuario=self.sem_aceite, tipo=Perfil.Tipo.PROFESSOR)

    def test_quem_nao_aceitou_e_barrado_em_rota_protegida(self):
        # Esta e a falha que o orientador apontou na entrega de 28/09 e que o
        # middleware passou a cobrir. So um teste de integracao pega isso.
        self.client.force_login(self.sem_aceite)

        resposta = self.client.get(reverse('lista_relatorios'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('aceitar_termos'), resposta['Location'])

    def test_a_tela_de_aceite_continua_aberta_para_quem_nao_aceitou(self):
        # Sem esta excecao a pessoa ficaria presa num ciclo de redirecionamento.
        self.client.force_login(self.sem_aceite)

        resposta = self.client.get(reverse('aceitar_termos'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Antes de continuar')

    def test_aceitar_grava_a_versao_e_libera_o_sistema(self):
        # Caminho feliz com efeito persistido.
        self.client.force_login(self.sem_aceite)

        resposta = self.client.post(reverse('aceitar_termos'), {'aceite': '1'})

        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(
            AceiteTermos.objects.filter(
                usuario=self.sem_aceite, versao=VERSAO_TERMOS,
            ).exists()
        )

        # E agora a rota que estava bloqueada abre.
        liberada = self.client.get(reverse('lista_relatorios'))
        self.assertEqual(liberada.status_code, 200)

    def test_sem_marcar_a_caixa_o_aceite_nao_e_gravado(self):
        # Cenario de erro: o formulario volta com aviso e nada e gravado.
        self.client.force_login(self.sem_aceite)

        resposta = self.client.post(reverse('aceitar_termos'), {})

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(AceiteTermos.objects.filter(usuario=self.sem_aceite).exists())


class FilaDeAprovacaoTest(BaseDeAcesso):
    """GET /acessos/pedidos/ e as acoes de aprovar e recusar."""

    def setUp(self):
        super().setUp()
        self.candidata = User.objects.create_user(
            username='ana.souza@example.com', email='ana.souza@example.com',
            password='SenhaForte2026', first_name='Ana', last_name='Souza',
            is_active=False,
        )
        self.pedido = SolicitacaoAcesso.objects.create(
            usuario=self.candidata, aluno=self.aluno,
            aceite_termos_em='2026-11-02 10:00:00+00:00',
        )

    def test_coordenador_ve_a_fila(self):
        self.client.force_login(self.coordenador)

        resposta = self.client.get(reverse('fila_aprovacao'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Ana')

    def test_responsavel_nao_abre_a_fila(self):
        # Seguranca: usuario autenticado, sem permissao para este recurso.
        responsavel = self._criar('bia.alves', Perfil.Tipo.RESPONSAVEL)
        self.client.force_login(responsavel)

        resposta = self.client.get(reverse('fila_aprovacao'))

        self.assertEqual(resposta.status_code, 403)
        self.assertContains(resposta, 'Forbidden', status_code=403)

    def test_visitante_anonimo_nao_abre_a_fila(self):
        # Seguranca: sem sessao.
        resposta = self.client.get(reverse('fila_aprovacao'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])

    def test_aprovar_por_get_e_recusado_com_405(self):
        # Cenario de erro com outro status: a acao muda estado, entao so POST.
        self.client.force_login(self.coordenador)

        resposta = self.client.get(
            reverse('aprovar_solicitacao', args=[self.pedido.pk])
        )

        self.assertEqual(resposta.status_code, 405)

    def test_recusar_por_get_e_recusado_com_405(self):
        # Quarto cenario de erro 4xx. Recusar muda estado, entao so POST.
        self.client.force_login(self.coordenador)

        resposta = self.client.get(
            reverse('recusar_solicitacao', args=[self.pedido.pk])
        )

        self.assertEqual(resposta.status_code, 405)

    @patch('acessos.views.enviar_email', return_value=(True, 'HTTP 201'))
    def test_aprovar_liga_a_conta_cria_perfil_e_vincula_o_aluno(self, email_falso):
        # Caminho feliz com efeito persistido em QUATRO lugares ao mesmo tempo.
        self.client.force_login(self.coordenador)

        resposta = self.client.post(
            reverse('aprovar_solicitacao', args=[self.pedido.pk])
        )

        self.assertEqual(resposta.status_code, 302)

        self.candidata.refresh_from_db()
        self.pedido.refresh_from_db()

        self.assertTrue(self.candidata.is_active)
        self.assertEqual(self.candidata.perfil.tipo, Perfil.Tipo.RESPONSAVEL)
        self.assertIn(self.aluno, self.candidata.perfil.alunos.all())
        self.assertEqual(self.pedido.status, SolicitacaoAcesso.Status.APROVADA)
        self.assertEqual(self.pedido.analisado_por, self.coordenador)
        # O aviso saiu pela API externa, que aqui esta mockada.
        email_falso.assert_called_once()

    @patch('acessos.views.enviar_email', return_value=(False, 'sem conexao'))
    def test_falha_no_email_nao_desfaz_a_aprovacao(self, email_falso):
        # A decisao da escola vale mesmo se o aviso nao sair. Esta e a regra
        # que justifica o envio ficar FORA da transacao.
        self.client.force_login(self.coordenador)

        self.client.post(reverse('aprovar_solicitacao', args=[self.pedido.pk]))

        self.candidata.refresh_from_db()
        self.assertTrue(self.candidata.is_active)

    @patch('acessos.views.enviar_email', return_value=(True, 'HTTP 201'))
    def test_recusar_sem_justificativa_nao_muda_o_pedido(self, email_falso):
        # Cenario de erro: a justificativa e obrigatoria.
        self.client.force_login(self.coordenador)

        self.client.post(reverse('recusar_solicitacao', args=[self.pedido.pk]), {})

        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, SolicitacaoAcesso.Status.PENDENTE)
        email_falso.assert_not_called()

    @patch('acessos.views.enviar_email', return_value=(True, 'HTTP 201'))
    def test_recusar_com_justificativa_registra_o_motivo(self, email_falso):
        self.client.force_login(self.coordenador)

        self.client.post(
            reverse('recusar_solicitacao', args=[self.pedido.pk]),
            {'justificativa': 'Vinculo nao confirmado pela secretaria'},
        )

        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, SolicitacaoAcesso.Status.RECUSADA)
        self.assertEqual(
            self.pedido.justificativa, 'Vinculo nao confirmado pela secretaria',
        )


class FluxoCompletoTest(BaseDeAcesso):
    """O fluxo que cruza dois recursos: acesso e relatorio."""

    @patch('acessos.views.enviar_email', return_value=(True, 'HTTP 201'))
    def test_do_cadastro_ate_o_responsavel_ler_o_relatorio_do_filho(self, _):
        # 1. A professora publica um relatorio na turma do Pedro.
        RelatorioDiario.objects.create(
            turma=self.turma, data_aula=date(2026, 11, 3),
            conteudo='Roda de leitura e contagem ate cem',
            autor=self.professora,
        )

        # 2. A mae se cadastra informando o RGM do filho.
        self.client.post(reverse('cadastro'), self.dados_do_cadastro())
        mae = User.objects.get(username='ana.souza@example.com')
        pedido = SolicitacaoAcesso.objects.get(usuario=mae)

        # 3. Antes da aprovacao, ela nao entra: a conta esta desligada.
        self.assertFalse(
            self.client.login(username='ana.souza@example.com',
                              password='SenhaForte2026')
        )

        # 4. A coordenacao aprova.
        self.client.force_login(self.coordenador)
        self.client.post(reverse('aprovar_solicitacao', args=[pedido.pk]))
        self.client.logout()

        # 5. Agora ela entra e enxerga o relatorio da turma do filho.
        self.assertTrue(
            self.client.login(username='ana.souza@example.com',
                              password='SenhaForte2026')
        )
        resposta = self.client.get(reverse('lista_relatorios'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Roda de leitura e contagem ate cem')
