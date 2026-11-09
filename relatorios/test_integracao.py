"""Testes de INTEGRACAO das rotas de relatorios.

Diferenca para os testes unitarios que ja existem em tests.py:

  - la usamos SimpleTestCase, que PROIBE o banco, e trocamos tudo por dubles;
  - aqui usamos TestCase, que CRIA um banco de teste de verdade, e nao trocamos
    nada: a requisicao entra pela URL, passa pelos middlewares, pela view, pelas
    regras de permissao, pelo ORM e chega ao banco.

O banco de teste e criado antes da suite e apagado no fim. Cada teste roda dentro
de uma transacao que e desfeita ao terminar, entao nenhum teste enxerga o que o
outro gravou.
"""

import urllib.request
from datetime import date

from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase, TestCase
from django.urls import reverse

from acessos.models import VERSAO_TERMOS, AceiteTermos
from auditoria.models import Evento
from relatorios.models import Aluno, Perfil, RelatorioDiario, Turma

User = get_user_model()


class BaseDeIntegracao(TestCase):
    """Monta o cenario comum: uma escola pequena, com gente de cada perfil."""

    def setUp(self):
        self.professora = self._criar('marcia.silva', Perfil.Tipo.PROFESSOR)
        self.coordenador = self._criar('joao.pereira', Perfil.Tipo.COORDENADOR)
        self.responsavel = self._criar('ana.souza', Perfil.Tipo.RESPONSAVEL)

        self.turma = Turma.objects.create(
            nome='3 ANO C', ano_letivo=2026, professor=self.professora,
        )
        self.outra_turma = Turma.objects.create(
            nome='5 ANO A', ano_letivo=2026, professor=self.coordenador,
        )
        self.aluno = Aluno.objects.create(
            nome_completo='Pedro Souza', rgm='2026001', turma=self.turma,
        )
        # A filha do responsavel: e por ela que ele enxerga a turma.
        self.responsavel.perfil.alunos.add(self.aluno)

    def _criar(self, usuario, tipo):
        pessoa = User.objects.create_user(
            username=usuario,
            email=f'{usuario}@example.com',
            password='senha-de-teste-123',
            first_name=usuario.split('.')[0].capitalize(),
            last_name='Teste',
        )
        Perfil.objects.create(usuario=pessoa, tipo=tipo)
        # Sem este registro o middleware ExigirAceiteTermos bloqueia tudo.
        AceiteTermos.objects.create(usuario=pessoa, versao=VERSAO_TERMOS)
        return pessoa

    def entrar_como(self, pessoa):
        self.client.force_login(pessoa)


class PaginaInicialTest(BaseDeIntegracao):
    """GET / — a vitrine publica."""

    def test_visitante_anonimo_recebe_a_pagina_publica(self):
        # Caminho feliz. Confere status E corpo, nao so o status.
        resposta = self.client.get(reverse('inicio'))

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'relatorios/inicio.html')
        self.assertContains(resposta, 'Elo Escolar')

    def test_quem_ja_entrou_e_levado_para_o_diario(self):
        # Caminho feliz com redirecionamento: confere o header Location.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('inicio'))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('lista_relatorios'))


class ListaRelatoriosTest(BaseDeIntegracao):
    """GET /relatorios/ — o diario de turma."""

    def setUp(self):
        super().setUp()
        self.relatorio = RelatorioDiario.objects.create(
            turma=self.turma,
            data_aula=date(2026, 11, 3),
            conteudo='Adicao com reserva',
            autor=self.professora,
        )
        self.relatorio_de_fora = RelatorioDiario.objects.create(
            turma=self.outra_turma,
            data_aula=date(2026, 11, 3),
            conteudo='Fracoes equivalentes',
            autor=self.coordenador,
        )

    def test_professora_ve_o_relatorio_da_turma_dela(self):
        # Caminho feliz: status e corpo.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('lista_relatorios'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Adicao com reserva')

    def test_professora_nao_ve_relatorio_de_turma_alheia(self):
        # A regra de visibilidade atravessando a pilha inteira ate o banco.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('lista_relatorios'))

        self.assertNotContains(resposta, 'Fracoes equivalentes')

    def test_visitante_anonimo_e_mandado_para_o_login(self):
        # Seguranca: sem sessao, nao entra. No Django a resposta e 302 para
        # a tela de login, e nao 401, porque a aplicacao e de paginas.
        resposta = self.client.get(reverse('lista_relatorios'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])


class CadastrarRelatorioTest(BaseDeIntegracao):
    """GET e POST /relatorios/novo/ — publicar o relatorio diario."""

    def dados_validos(self, **troca):
        dados = {
            'turma': self.turma.id,
            'data_aula': '2026-11-03',
            'conteudo': 'Leitura compartilhada e roda de conversa',
            'tarefa_descricao': 'Ler as paginas 20 e 21',
            'tarefa_data_entrega': '2026-11-04',
            'observacoes': '',
        }
        dados.update(troca)
        return dados

    def test_professora_abre_o_formulario(self):
        # Caminho feliz do GET.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('cadastrar_relatorio'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Conteúdo trabalhado')

    def test_professora_publica_e_o_relatorio_fica_gravado(self):
        # Caminho feliz do POST, com as tres verificacoes que o enunciado pede:
        # status, header de redirecionamento e EFEITO PERSISTIDO no banco.
        self.entrar_como(self.professora)

        resposta = self.client.post(
            reverse('cadastrar_relatorio'), self.dados_validos(),
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('lista_relatorios'))

        gravado = RelatorioDiario.objects.get(data_aula=date(2026, 11, 3))
        self.assertEqual(gravado.conteudo,
                         'Leitura compartilhada e roda de conversa')
        self.assertEqual(gravado.turma, self.turma)
        # A autoria vem da sessao, nunca do formulario.
        self.assertEqual(gravado.autor, self.professora)

    def test_responsavel_tentando_publicar_recebe_403(self):
        # Seguranca: usuario autenticado, mas sem permissao para esta acao.
        self.entrar_como(self.responsavel)

        resposta = self.client.post(
            reverse('cadastrar_relatorio'), self.dados_validos(),
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertContains(resposta, 'Forbidden', status_code=403)
        self.assertEqual(RelatorioDiario.objects.count(), 0)

    def test_turma_de_outro_professor_e_recusada_pelo_formulario(self):
        # Cenario de erro: mesmo forjando o id de uma turma que a professora
        # nao enxerga, o formulario recusa, porque o queryset foi restrito.
        self.entrar_como(self.professora)

        resposta = self.client.post(
            reverse('cadastrar_relatorio'),
            self.dados_validos(turma=self.outra_turma.id),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Faça uma escolha válida')
        self.assertEqual(RelatorioDiario.objects.count(), 0)

    def test_formulario_sem_conteudo_nao_grava_nada(self):
        # Cenario de erro: campo obrigatorio vazio.
        self.entrar_como(self.professora)

        resposta = self.client.post(
            reverse('cadastrar_relatorio'), self.dados_validos(conteudo=''),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(RelatorioDiario.objects.count(), 0)

    def test_visitante_anonimo_nao_abre_o_formulario(self):
        # Seguranca: terceiro caso do trio exigido pelo enunciado.
        resposta = self.client.get(reverse('cadastrar_relatorio'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])


class EditarExcluirRelatorioTest(BaseDeIntegracao):
    """RF11 — editar e excluir relatorio ja publicado.

    Tres regras de negocio atravessadas aqui: quem corrige (autor e gestao),
    como se exclui (logicamente, sem apagar a linha) e o aviso de alteracao
    na tela de quem le.
    """

    def setUp(self):
        super().setUp()
        self.relatorio = RelatorioDiario.objects.create(
            turma=self.turma,
            data_aula=date(2026, 11, 3),
            conteudo='Adicao com reserva',
            autor=self.professora,
        )

    def url_editar(self):
        return reverse('editar_relatorio', args=[self.relatorio.id])

    def url_excluir(self):
        return reverse('excluir_relatorio', args=[self.relatorio.id])

    def dados_corrigidos(self, **troca):
        dados = {
            'turma': self.turma.id,
            'data_aula': '2026-11-03',
            'conteudo': 'Adicao com reserva e problemas do cotidiano',
            'tarefa_descricao': '',
            'tarefa_data_entrega': '',
            'observacoes': '',
        }
        dados.update(troca)
        return dados

    def test_professora_abre_o_formulario_com_o_texto_atual(self):
        # Caminho feliz do GET: o formulario tem de vir preenchido, senao a
        # pessoa reescreveria tudo do zero.
        self.entrar_como(self.professora)

        resposta = self.client.get(self.url_editar())

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Adicao com reserva')

    def test_professora_corrige_o_proprio_relatorio(self):
        # Caminho feliz do POST, com efeito persistido: o texto muda no banco
        # e a marca de alteracao e gravada.
        self.entrar_como(self.professora)

        resposta = self.client.post(self.url_editar(), self.dados_corrigidos())

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('lista_relatorios'))

        self.relatorio.refresh_from_db()
        self.assertEqual(
            self.relatorio.conteudo,
            'Adicao com reserva e problemas do cotidiano',
        )
        self.assertIsNotNone(self.relatorio.editado_em)
        self.assertEqual(self.relatorio.editado_por, self.professora)

    def test_coordenador_corrige_relatorio_de_outra_pessoa(self):
        # A gestao corrige qualquer um, e a autoria original nao muda.
        self.entrar_como(self.coordenador)

        resposta = self.client.post(self.url_editar(), self.dados_corrigidos())

        self.assertEqual(resposta.status_code, 302)

        self.relatorio.refresh_from_db()
        self.assertEqual(self.relatorio.editado_por, self.coordenador)
        self.assertEqual(self.relatorio.autor, self.professora)

    def test_responsavel_nao_abre_a_edicao(self):
        # Seguranca: autenticado, porem sem permissao para esta acao.
        self.entrar_como(self.responsavel)

        resposta = self.client.get(self.url_editar())

        self.assertEqual(resposta.status_code, 403)
        self.assertContains(resposta, 'Forbidden', status_code=403)

    def test_o_selo_de_alteracao_aparece_na_lista(self):
        # A terceira regra de negocio, vista pelos olhos de quem le.
        self.entrar_como(self.professora)
        self.client.post(self.url_editar(), self.dados_corrigidos())

        resposta = self.client.get(reverse('lista_relatorios'))

        self.assertContains(resposta, 'Editado em')

    def test_relatorio_novo_nao_mostra_selo_de_alteracao(self):
        # O contraponto do teste acima: sem edicao, nada de selo.
        self.entrar_como(self.professora)

        resposta = self.client.get(reverse('lista_relatorios'))

        self.assertNotContains(resposta, 'Editado em')

    def test_excluir_por_get_e_recusado_com_405(self):
        # Cenario de erro: acao que muda o estado do sistema nao acontece por
        # um endereco digitado na barra do navegador.
        self.entrar_como(self.coordenador)

        resposta = self.client.get(self.url_excluir())

        self.assertEqual(resposta.status_code, 405)

    def test_coordenador_exclui_e_o_registro_continua_no_banco(self):
        # O coracao da exclusao logica: some da tela, permanece no banco com
        # a data e o nome de quem excluiu.
        self.entrar_como(self.coordenador)

        resposta = self.client.post(self.url_excluir())

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], reverse('lista_relatorios'))

        self.assertTrue(
            RelatorioDiario.objects.filter(pk=self.relatorio.pk).exists(),
            'a linha nao pode sair do banco: a exclusao e logica',
        )
        self.relatorio.refresh_from_db()
        self.assertTrue(self.relatorio.excluido)
        self.assertIsNotNone(self.relatorio.excluido_em)
        self.assertEqual(self.relatorio.excluido_por, self.coordenador)

        lista = self.client.get(reverse('lista_relatorios'))
        self.assertNotContains(lista, 'Adicao com reserva')

    def test_professora_nao_exclui_nem_o_proprio_relatorio(self):
        # Seguranca: corrigir e do autor, retirar do ar e da gestao.
        self.entrar_como(self.professora)

        resposta = self.client.post(self.url_excluir())

        self.assertEqual(resposta.status_code, 403)

        self.relatorio.refresh_from_db()
        self.assertFalse(self.relatorio.excluido)

    def test_editar_relatorio_ja_excluido_devolve_404(self):
        # Cenario de erro: para quem edita, o relatorio excluido simplesmente
        # nao existe mais.
        self.relatorio.excluido = True
        self.relatorio.save(update_fields=['excluido'])
        self.entrar_como(self.coordenador)

        resposta = self.client.get(self.url_editar())

        self.assertEqual(resposta.status_code, 404)

    def test_a_auditoria_registra_a_edicao_e_a_exclusao(self):
        # Rastreabilidade: as duas acoes novas precisam deixar marca no log.
        self.entrar_como(self.coordenador)

        self.client.post(self.url_editar(), self.dados_corrigidos())
        self.client.post(self.url_excluir())

        self.assertEqual(
            Evento.objects.filter(
                acao=Evento.Acao.RELATORIO_EDITADO,
                usuario=self.coordenador,
            ).count(),
            1,
        )
        self.assertEqual(
            Evento.objects.filter(
                acao=Evento.Acao.RELATORIO_EXCLUIDO,
                usuario=self.coordenador,
            ).count(),
            1,
        )


class SemRedirecionar(urllib.request.HTTPErrorProcessor):
    """Faz o urlopen devolver 3xx e 4xx em vez de estourar excecao.

    O enunciado pede um cliente HTTP que nao quebre em erro, para que o status
    possa ser conferido por assercao. No Spring isso e o defaultStatusHandler;
    aqui e esta classe de tres linhas.
    """

    def http_response(self, requisicao, resposta):
        return resposta

    https_response = http_response


class HttpRealTest(LiveServerTestCase):
    """Testes por HTTP de verdade, em porta aleatoria.

    As outras classes usam o cliente de teste do Django, que chama a aplicacao
    dentro do proprio processo. Esta sobe um servidor de verdade numa porta
    livre escolhida na hora e faz a requisicao pela rede. E o equivalente, no
    Django, ao @SpringBootTest(webEnvironment = RANDOM_PORT) com RestClient que
    o enunciado exige em pelo menos uma classe.

    Como a porta e sorteada a cada execucao, estes testes continuam passando
    mesmo com a aplicacao de desenvolvimento rodando na 8000.
    """

    def buscar(self, caminho):
        cliente = urllib.request.build_opener(SemRedirecionar)
        with cliente.open(self.live_server_url + caminho) as resposta:
            corpo = resposta.read().decode('utf-8')
            return resposta.status, corpo, resposta.headers

    def test_vitrine_publica_responde_por_http_real(self):
        # Caminho feliz: status e corpo, vindos de uma requisicao de rede.
        status, corpo, _ = self.buscar('/')

        self.assertEqual(status, 200)
        self.assertIn('Elo Escolar', corpo)

    def test_rota_protegida_devolve_302_para_o_login_por_http_real(self):
        # Seguranca conferida pela rede: sem sessao, o servidor responde 302
        # e o header Location aponta para a tela de login.
        status, _, cabecalhos = self.buscar('/relatorios/')

        self.assertEqual(status, 302)
        self.assertIn(reverse('login'), cabecalhos['Location'])
