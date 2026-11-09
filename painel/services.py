"""Os numeros e os graficos do painel (RF12).

Este arquivo nao desenha nada e nao sabe o que e uma pagina. Ele so faz
contas sobre o que ja existe no banco e devolve numeros prontos. A view
pergunta, este arquivo responde - o mesmo desenho que o projeto usa para
permissao.

Separar assim tem um motivo pratico: da para testar cada conta isoladamente,
sem abrir tela nenhuma.
"""

from datetime import date, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncWeek

from acessos.models import SolicitacaoAcesso
from acessos.permissions import (
    pode_aprovar_acessos,
    solicitacoes_que_pode_analisar,
)
from recados.permissions import recados_visiveis
from relatorios.models import RelatorioDiario
from relatorios.permissions import (
    eh_responsavel,
    obter_perfil,
    turmas_visiveis,
)

# Janela padrao dos indicadores. Trinta dias cobre um mes letivo inteiro.
PERIODO_DIAS = 30

# Quantas semanas o grafico de linha mostra.
SEMANAS_NO_GRAFICO = 8

# Prazo da tarefa que ainda interessa a familia.
DIAS_DE_TAREFA = 7


def relatorios_visiveis(user):
    """Relatorios das turmas que a pessoa enxerga, sem os excluidos.

    Reaproveita turmas_visiveis, que ja e a regra do sistema inteiro. O
    painel nao inventa uma segunda regra de visibilidade - se inventasse,
    um dia as duas discordariam e o painel mostraria numero de dado que a
    pessoa nao pode ver.
    """
    return RelatorioDiario.objects.filter(
        turma__in=turmas_visiveis(user), excluido=False,
    )


def indicadores(user):
    """Os Big Numbers. Lista de dicionarios, prontos para o template.

    O painel muda conforme o perfil: a familia quer saber o que precisa
    fazer; a escola quer saber o que precisa acompanhar.
    """
    perfil = obter_perfil(user)

    if perfil is None or not user.is_active:
        return []

    if eh_responsavel(user):
        return _indicadores_da_familia(user)

    return _indicadores_da_escola(user)


def _indicadores_da_escola(user):
    desde = date.today() - timedelta(days=PERIODO_DIAS)

    pendentes = 0
    if pode_aprovar_acessos(user):
        pendentes = solicitacoes_que_pode_analisar(user).filter(
            status=SolicitacaoAcesso.Status.PENDENTE,
        ).count()

    return [
        {
            'rotulo': 'Relatórios nos últimos 30 dias',
            'valor': relatorios_visiveis(user).filter(
                data_aula__gte=desde,
            ).count(),
            'nota': 'Aulas registradas no diário',
        },
        {
            'rotulo': 'Turmas acompanhadas',
            'valor': turmas_visiveis(user).count(),
            'nota': 'Turmas que você enxerga no sistema',
        },
        {
            'rotulo': 'Recados no mural',
            'valor': _recados_no_ar(user).count(),
            'nota': 'Avisos dentro do prazo de exibição',
        },
        {
            'rotulo': 'Pedidos de acesso pendentes',
            'valor': pendentes,
            'nota': 'Famílias esperando aprovação',
        },
    ]


def _indicadores_da_familia(user):
    hoje = date.today()
    desde = hoje - timedelta(days=PERIODO_DIAS)
    ate = hoje + timedelta(days=DIAS_DE_TAREFA)

    tarefas = relatorios_visiveis(user).filter(
        tarefa_data_entrega__gte=hoje,
        tarefa_data_entrega__lte=ate,
    ).exclude(tarefa_descricao='')

    return [
        {
            'rotulo': 'Relatórios nos últimos 30 dias',
            'valor': relatorios_visiveis(user).filter(
                data_aula__gte=desde,
            ).count(),
            'nota': 'Aulas registradas pela escola',
        },
        {
            'rotulo': 'Tarefas desta semana',
            'valor': tarefas.count(),
            'nota': 'Com entrega nos próximos 7 dias',
        },
        {
            'rotulo': 'Recados no mural',
            'valor': _recados_no_ar(user).count(),
            'nota': 'Avisos dentro do prazo de exibição',
        },
        {
            'rotulo': 'Estudantes acompanhados',
            'valor': user.perfil.alunos.count(),
            'nota': 'Vínculos aprovados pela escola',
        },
    ]


def _recados_no_ar(user):
    """Só os recados dentro do prazo.

    recados_visiveis ja descarta os vencidos para a familia, mas devolve os
    encerrados para a equipe da escola, que precisa enxergar o historico. O
    indicador conta so o que esta no mural agora, entao o prazo e conferido
    aqui de novo - para os dois perfis, de uma vez.
    """
    no_ar = Q(exibir_ate__isnull=True) | Q(exibir_ate__gte=date.today())
    return recados_visiveis(user).filter(no_ar)


def relatorios_por_turma(user):
    """Dados do grafico de barras: quantos relatorios cada turma recebeu.

    Devolve rotulos e valores em duas listas paralelas, que e o formato que
    o Chart.js espera.
    """
    desde = date.today() - timedelta(days=PERIODO_DIAS)

    linhas = (
        relatorios_visiveis(user)
        .filter(data_aula__gte=desde)
        .values('turma__nome')
        .annotate(quantidade=Count('id'))
        .order_by('turma__nome')
    )

    return {
        'rotulos': [linha['turma__nome'] for linha in linhas],
        'valores': [linha['quantidade'] for linha in linhas],
    }


def relatorios_por_semana(user):
    """Dados do grafico de linha: ritmo de publicacao nas ultimas semanas.

    As semanas sem nenhum relatorio precisam aparecer como zero, senao o
    grafico mente: uma semana vazia sumiria e o periodo pareceria continuo.
    Por isso montamos a lista completa de semanas e so depois preenchemos.
    """
    hoje = date.today()
    inicio = hoje - timedelta(weeks=SEMANAS_NO_GRAFICO - 1)
    # Segunda-feira da semana mais antiga que entra no grafico.
    primeira_segunda = inicio - timedelta(days=inicio.weekday())

    contagem = {}
    linhas = (
        relatorios_visiveis(user)
        .filter(data_aula__gte=primeira_segunda)
        .annotate(semana=TruncWeek('data_aula'))
        .values('semana')
        .annotate(quantidade=Count('id'))
    )
    for linha in linhas:
        contagem[linha['semana']] = linha['quantidade']

    rotulos = []
    valores = []
    for passo in range(SEMANAS_NO_GRAFICO):
        segunda = primeira_segunda + timedelta(weeks=passo)
        rotulos.append(segunda.strftime('%d/%m'))
        valores.append(contagem.get(segunda, 0))

    return {'rotulos': rotulos, 'valores': valores}
