"""Testes da tela de consulta do log de auditoria (RF07).

O log mostra o que todo mundo fez. Por isso o que mais importa aqui nao e
a listagem em si, e sim quem consegue abri-la.
"""

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, tag
from django.urls import reverse

from acessos.models import VERSAO_TERMOS, AceiteTermos
from auditoria.models import Evento
from auditoria.permissions import pode_consultar_log
from relatorios.models import Perfil

User = get_user_model()

SENHA = 'senha-de-teste-123'


def usuario_falso(tipo, ativo=True):
    from types import SimpleNamespace
    return SimpleNamespace(
        is_authenticated=True,
        is_active=ativo,
        perfil=SimpleNamespace(tipo=tipo),
    )


class PodeConsultarLogTest(SimpleTestCase):
    """Teste unitario: a regra isolada, sem banco e sem tela."""

    def test_diretor_consulta(self):
        self.assertTrue(pode_consultar_log(usuario_falso(Perfil.Tipo.DIRETOR)))

    def test_coordenador_consulta(self):
        self.assertTrue(
            pode_consultar_log(usuario_falso(Perfil.Tipo.COORDENADOR))
        )

    def test_professor_nao_consulta(self):
        # Fronteira da regra: o professor responde pelo proprio trabalho;
        # o log mostra o dos colegas tambem.
        self.assertFalse(
            pode_consultar_log(usuario_falso(Perfil.Tipo.PROFESSOR))
        )

    def test_responsavel_nao_consulta(self):
        self.assertFalse(
            pode_consultar_log(usuario_falso(Perfil.Tipo.RESPONSAVEL))
        )

    def test_conta_desativada_nao_consulta(self):
        # Caso-limite: muda so o is_active.
        self.assertFalse(
            pode_consultar_log(usuario_falso(Perfil.Tipo.DIRETOR, ativo=False))
        )

    def test_usuario_sem_perfil_nao_consulta(self):
        # "Negue por padrao."
        from types import SimpleNamespace
        self.assertFalse(pode_consultar_log(
            SimpleNamespace(is_authenticated=True, is_active=True)
        ))


# A etiqueta vale tambem para as classes que herdam desta.
@tag('integracao')
class TelaDoLogTest(TestCase):
    """A requisicao entrando pela URL, atravessando regra, ORM e banco."""

    def setUp(self):
        self.diretora = self._criar('ana.diretora', Perfil.Tipo.DIRETOR)
        self.professora = self._criar('marcia.silva', Perfil.Tipo.PROFESSOR)

        Evento.objects.create(
            acao=Evento.Acao.RELATORIO_PUBLICADO, usuario=self.professora,
        )
        Evento.objects.create(
            acao=Evento.Acao.LOGIN_FALHA,
            usuario_informado='invasor@example.com',
            detalhe='origem 203.0.113.9',
        )

    def _criar(self, nome, tipo):
        pessoa = User.objects.create_user(
            username=f'{nome}@example.com', email=f'{nome}@example.com',
            password=SENHA, first_name=nome.split('.')[0].capitalize(),
            last_name='Teste',
        )
        Perfil.objects.create(usuario=pessoa, tipo=tipo)
        AceiteTermos.objects.create(usuario=pessoa, versao=VERSAO_TERMOS)
        return pessoa

    def test_diretora_abre_o_log_e_ve_os_eventos(self):
        # Caminho feliz: status E corpo.
        self.client.force_login(self.diretora)

        resposta = self.client.get(reverse('log_auditoria'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Log de auditoria')
        self.assertContains(resposta, 'Publicou relatório')
        self.assertContains(resposta, 'invasor@example.com')

    def test_professora_recebe_403(self):
        # Seguranca: usuario autenticado, sem permissao para este recurso.
        # E o defeito que esta tela veio corrigir: antes, o item do menu
        # levava ao painel administrativo do Django e a propria diretora
        # tomava 403.
        self.client.force_login(self.professora)

        resposta = self.client.get(reverse('log_auditoria'))

        self.assertEqual(resposta.status_code, 403)

    def test_visitante_anonimo_e_mandado_para_a_entrada(self):
        resposta = self.client.get(reverse('log_auditoria'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])

    def test_o_menu_mostra_o_log_para_a_gestao(self):
        self.client.force_login(self.diretora)

        resposta = self.client.get(reverse('painel'))

        self.assertContains(resposta, reverse('log_auditoria'))

    def test_o_menu_esconde_o_log_do_professor(self):
        # Esconder na tela e usabilidade; o 403 acima e a seguranca. O
        # sistema faz as duas coisas, e sao coisas diferentes.
        self.client.force_login(self.professora)

        resposta = self.client.get(reverse('painel'))

        self.assertNotContains(resposta, reverse('log_auditoria'))

    def test_filtro_por_acao(self):
        self.client.force_login(self.diretora)

        resposta = self.client.get(
            reverse('log_auditoria'), {'acao': Evento.Acao.LOGIN_FALHA},
        )

        self.assertContains(resposta, 'invasor@example.com')
        # Nao se verifica pelo rotulo da acao: ele aparece tambem na
        # lista de opcoes do filtro, que e desenhada sempre. O que prova
        # o filtro e a ausencia do autor do outro evento na tabela.
        self.assertNotContains(resposta, 'marcia.silva@example.com')
        self.assertContains(resposta, '1 evento encontrado')

    def test_acao_inventada_e_ignorada_em_vez_de_quebrar(self):
        # Cenario de erro: valor que nao existe entre as opcoes nao chega
        # a ir para a consulta.
        self.client.force_login(self.diretora)

        resposta = self.client.get(
            reverse('log_auditoria'), {'acao': 'NAO_EXISTE'},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Publicou relatório')

    def test_busca_por_pessoa(self):
        self.client.force_login(self.diretora)

        resposta = self.client.get(reverse('log_auditoria'), {'q': 'invasor'})

        self.assertContains(resposta, 'invasor@example.com')
        self.assertNotContains(resposta, 'marcia.silva@example.com')
        self.assertContains(resposta, '1 evento encontrado')

    def test_busca_sem_resultado_mostra_a_tela_vazia(self):
        self.client.force_login(self.diretora)

        resposta = self.client.get(
            reverse('log_auditoria'), {'q': 'ninguem-com-esse-nome'},
        )

        self.assertContains(resposta, 'Nenhum evento encontrado')
