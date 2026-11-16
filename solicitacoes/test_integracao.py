"""Testes de INTEGRACAO das solicitacoes (RF10).

Banco de teste de verdade, requisicao entrando pela URL e atravessando
middleware, view, permissoes e ORM. So a chamada a API externa de e-mail e
substituida por duble, por ser dependencia externa.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from django.urls import reverse

from acessos.models import VERSAO_TERMOS, AceiteTermos
from auditoria.models import Evento
from relatorios.models import Aluno, Perfil, Turma
from solicitacoes.models import Solicitacao

User = get_user_model()


# A etiqueta vale tambem para as classes que herdam desta: no Django, a
# marcacao e herdada pelas subclasses. Por isso basta etiquetar a base.
@tag('integracao')
class BaseDeSolicitacoes(TestCase):
    """Uma escola com duas turmas e duas familias distintas."""

    def setUp(self):
        self.professora = self._criar('marcia.silva', Perfil.Tipo.PROFESSOR)
        self.coordenador = self._criar('joao.pereira', Perfil.Tipo.COORDENADOR)
        self.responsavel = self._criar('ana.souza', Perfil.Tipo.RESPONSAVEL)
        self.outro_responsavel = self._criar(
            'paulo.lima', Perfil.Tipo.RESPONSAVEL,
        )

        self.turma = Turma.objects.create(
            nome='3 ANO C', ano_letivo=2026, professor=self.professora,
        )
        self.outra_turma = Turma.objects.create(
            nome='5 ANO A', ano_letivo=2026, professor=self.coordenador,
        )
        self.aluno = Aluno.objects.create(
            nome_completo='Pedro Souza', rgm='2026001', turma=self.turma,
        )
        self.aluno_de_fora = Aluno.objects.create(
            nome_completo='Clara Lima', rgm='2026002', turma=self.outra_turma,
        )
        self.responsavel.perfil.alunos.add(self.aluno)
        self.outro_responsavel.perfil.alunos.add(self.aluno_de_fora)

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

    def entrar_como(self, pessoa):
        self.client.force_login(pessoa)

    def solicitacao(self, autor=None, aluno=None, **troca):
        dados = {
            'aluno': aluno or self.aluno,
            'autor': autor or self.responsavel,
            'tipo': Solicitacao.Tipo.JUSTIFICATIVA,
            'assunto': 'Falta na segunda-feira',
            'descricao': 'O Pedro faltou por consulta de rotina.',
        }
        dados.update(troca)
        return Solicitacao.objects.create(**dados)

    def dados_validos(self, **troca):
        dados = {
            'aluno': self.aluno.id,
            'tipo': Solicitacao.Tipo.JUSTIFICATIVA,
            'assunto': 'Falta na segunda-feira',
            'descricao': 'O Pedro faltou por consulta de rotina.',
        }
        dados.update(troca)
        return dados


class AbrirSolicitacaoTest(BaseDeSolicitacoes):

    def test_responsavel_abre_o_formulario(self):
        # Caminho feliz do GET: status e corpo.
        self.entrar_como(self.responsavel)

        resposta = self.client.get(reverse('abrir_solicitacao'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Sobre qual estudante')

    def test_responsavel_abre_solicitacao_e_ela_fica_gravada(self):
        # Caminho feliz do POST, com efeito persistido.
        self.entrar_como(self.responsavel)

        resposta = self.client.post(
            reverse('abrir_solicitacao'), self.dados_validos(),
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('lista_solicitacoes'))

        gravada = Solicitacao.objects.get(assunto='Falta na segunda-feira')
        # A autoria vem da sessao, nunca do formulario.
        self.assertEqual(gravada.autor, self.responsavel)
        self.assertEqual(gravada.situacao, Solicitacao.Situacao.ABERTA)
        self.assertIsNone(gravada.respondida_em)

    def test_responsavel_nao_abre_solicitacao_sobre_crianca_alheia(self):
        # Seguranca: mesmo forjando o id de outro aluno, o formulario recusa,
        # porque a lista foi restrita aos filhos de quem esta na tela.
        self.entrar_como(self.responsavel)

        resposta = self.client.post(
            reverse('abrir_solicitacao'),
            self.dados_validos(aluno=self.aluno_de_fora.id),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Solicitacao.objects.count(), 0)

    def test_professor_nao_abre_solicitacao(self):
        # Seguranca: autenticado, porem sem permissao para esta acao.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('abrir_solicitacao'))

        self.assertEqual(resposta.status_code, 403)
        self.assertContains(resposta, 'Forbidden', status_code=403)

    def test_solicitacao_sem_descricao_nao_e_gravada(self):
        # Cenario de erro: campo obrigatorio vazio.
        self.entrar_como(self.responsavel)

        resposta = self.client.post(
            reverse('abrir_solicitacao'), self.dados_validos(descricao=''),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Solicitacao.objects.count(), 0)

    def test_visitante_anonimo_e_mandado_para_o_login(self):
        resposta = self.client.get(reverse('lista_solicitacoes'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])

    def test_a_auditoria_registra_a_abertura(self):
        self.entrar_como(self.responsavel)

        self.client.post(reverse('abrir_solicitacao'), self.dados_validos())

        self.assertEqual(
            Evento.objects.filter(
                acao=Evento.Acao.SOLICITACAO_ABERTA,
                usuario=self.responsavel,
            ).count(),
            1,
        )


class VisibilidadeTest(BaseDeSolicitacoes):

    def test_professora_ve_solicitacao_da_turma_dela(self):
        # Caminho feliz: status e corpo.
        self.solicitacao()
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('lista_solicitacoes'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Falta na segunda-feira')

    def test_professora_nao_ve_solicitacao_de_turma_alheia(self):
        # Seguranca: a regra de visibilidade atravessando a pilha ate o banco.
        self.solicitacao(
            autor=self.outro_responsavel, aluno=self.aluno_de_fora,
            assunto='Pedido do 5 ANO A',
        )
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('lista_solicitacoes'))

        self.assertNotContains(resposta, 'Pedido do 5 ANO A')

    def test_coordenador_ve_as_duas_turmas(self):
        # O contraponto: a gestao supervisiona todas.
        self.solicitacao()
        self.solicitacao(
            autor=self.outro_responsavel, aluno=self.aluno_de_fora,
            assunto='Pedido do 5 ANO A',
        )
        self.entrar_como(self.coordenador)

        resposta = self.client.get(reverse('lista_solicitacoes'))

        self.assertContains(resposta, 'Falta na segunda-feira')
        self.assertContains(resposta, 'Pedido do 5 ANO A')

    def test_familia_nao_ve_solicitacao_de_outra_familia(self):
        # Decisao de projeto: duas pessoas podem ser responsaveis pela mesma
        # crianca, e o que uma escreveu a escola nao e da outra.
        self.solicitacao(assunto='Assunto da Ana')
        self.entrar_como(self.outro_responsavel)

        resposta = self.client.get(reverse('lista_solicitacoes'))

        self.assertNotContains(resposta, 'Assunto da Ana')


class ResponderSolicitacaoTest(BaseDeSolicitacoes):

    def url(self, solicitacao):
        return reverse('responder_solicitacao', args=[solicitacao.id])

    @patch('solicitacoes.views.enviar_email', return_value=(True, 'HTTP 201'))
    def test_professora_responde_e_a_situacao_muda(self, _email):
        # Caminho feliz do POST com efeito persistido.
        pedido = self.solicitacao()
        self.entrar_como(self.professora)

        resposta = self.client.post(
            self.url(pedido), {'texto': 'Falta justificada, obrigado pelo '
                                        'aviso.'},
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('lista_solicitacoes'))

        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, Solicitacao.Situacao.RESPONDIDA)
        self.assertEqual(pedido.respondida_por, self.professora)
        self.assertIsNotNone(pedido.respondida_em)

    @patch('solicitacoes.views.enviar_email', return_value=(True, 'HTTP 201'))
    def test_responder_dispara_o_aviso_por_email(self, email_falso):
        pedido = self.solicitacao()
        self.entrar_como(self.professora)

        self.client.post(self.url(pedido), {'texto': 'Falta justificada.'})

        email_falso.assert_called_once()
        self.assertEqual(
            email_falso.call_args.args[0], self.responsavel.email,
        )

    @patch('solicitacoes.views.enviar_email',
           return_value=(False, 'sem conexao'))
    def test_falha_no_email_nao_desfaz_a_resposta(self, _email):
        # Mesmo tratamento de excecao do RF04: a decisao ja esta gravada.
        pedido = self.solicitacao()
        self.entrar_como(self.professora)

        resposta = self.client.post(
            self.url(pedido), {'texto': 'Falta justificada.'},
        )

        self.assertEqual(resposta.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, Solicitacao.Situacao.RESPONDIDA)

    def test_professora_nao_responde_solicitacao_de_turma_alheia(self):
        # Seguranca: permissao de objeto, nao apenas de perfil.
        pedido = self.solicitacao(
            autor=self.outro_responsavel, aluno=self.aluno_de_fora,
        )
        self.entrar_como(self.professora)

        resposta = self.client.post(self.url(pedido), {'texto': 'Qualquer.'})

        self.assertEqual(resposta.status_code, 403)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, Solicitacao.Situacao.ABERTA)

    def test_responsavel_nao_responde_a_propria_solicitacao(self):
        # Seguranca: quem abre nao responde em nome da escola.
        pedido = self.solicitacao()
        self.entrar_como(self.responsavel)

        resposta = self.client.get(self.url(pedido))

        self.assertEqual(resposta.status_code, 403)

    def test_resposta_curta_demais_e_recusada(self):
        # Cenario de erro: validacao propria do formulario.
        pedido = self.solicitacao()
        self.entrar_como(self.professora)

        resposta = self.client.post(self.url(pedido), {'texto': 'ok'})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'pelo menos 10 caracteres')
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, Solicitacao.Situacao.ABERTA)

    @patch('solicitacoes.views.enviar_email', return_value=(True, 'HTTP 201'))
    def test_a_auditoria_registra_a_resposta(self, _email):
        pedido = self.solicitacao()
        self.entrar_como(self.professora)

        self.client.post(self.url(pedido), {'texto': 'Falta justificada.'})

        self.assertEqual(
            Evento.objects.filter(
                acao=Evento.Acao.SOLICITACAO_RESPONDIDA,
                usuario=self.professora,
            ).count(),
            1,
        )


class EncerrarSolicitacaoTest(BaseDeSolicitacoes):

    def url(self, solicitacao):
        return reverse('encerrar_solicitacao', args=[solicitacao.id])

    def respondida(self):
        pedido = self.solicitacao()
        pedido.responder(self.professora, 'Falta justificada, obrigado.')
        return pedido

    def test_autor_encerra_depois_de_respondida(self):
        # Caminho feliz com efeito persistido.
        pedido = self.respondida()
        self.entrar_como(self.responsavel)

        resposta = self.client.post(self.url(pedido))

        self.assertEqual(resposta.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, Solicitacao.Situacao.ENCERRADA)
        self.assertIsNotNone(pedido.encerrada_em)

    def test_encerrar_por_get_e_recusado_com_405(self):
        # Cenario de erro: acao que muda o estado nao acontece por um
        # endereco digitado na barra do navegador.
        pedido = self.respondida()
        self.entrar_como(self.responsavel)

        resposta = self.client.get(self.url(pedido))

        self.assertEqual(resposta.status_code, 405)

    def test_nao_se_encerra_pedido_ainda_sem_resposta(self):
        # Fronteira da regra.
        pedido = self.solicitacao()
        self.entrar_como(self.responsavel)

        resposta = self.client.post(self.url(pedido))

        self.assertEqual(resposta.status_code, 403)
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, Solicitacao.Situacao.ABERTA)

    def test_professora_nao_encerra_pedido_da_familia(self):
        # Encerrar e dizer "estou satisfeito", e isso e de quem pediu.
        pedido = self.respondida()
        self.entrar_como(self.professora)

        resposta = self.client.post(self.url(pedido))

        self.assertEqual(resposta.status_code, 403)

    def test_pedido_encerrado_nao_recebe_resposta_nova(self):
        pedido = self.respondida()
        pedido.encerrar()
        self.entrar_como(self.professora)

        resposta = self.client.post(
            reverse('responder_solicitacao', args=[pedido.id]),
            {'texto': 'Mais uma observacao.'},
        )

        self.assertEqual(resposta.status_code, 403)


class FluxoCompletoTest(BaseDeSolicitacoes):

    @patch('solicitacoes.views.enviar_email', return_value=(True, 'HTTP 201'))
    def test_da_abertura_ao_encerramento(self, _email):
        # O requisito inteiro de ponta a ponta: a familia abre, a escola
        # responde, a familia encerra.
        self.entrar_como(self.responsavel)
        self.client.post(reverse('abrir_solicitacao'), self.dados_validos())
        pedido = Solicitacao.objects.get()
        self.assertEqual(pedido.situacao, Solicitacao.Situacao.ABERTA)

        self.entrar_como(self.professora)
        self.client.post(
            reverse('responder_solicitacao', args=[pedido.id]),
            {'texto': 'Falta justificada, obrigado pelo aviso.'},
        )
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, Solicitacao.Situacao.RESPONDIDA)

        self.entrar_como(self.responsavel)
        lista = self.client.get(reverse('lista_solicitacoes'))
        self.assertContains(lista, 'Falta justificada')

        self.client.post(reverse('encerrar_solicitacao', args=[pedido.id]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.situacao, Solicitacao.Situacao.ENCERRADA)
