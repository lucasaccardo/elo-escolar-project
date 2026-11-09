"""Quem publica e quem enxerga recado.

Mesma ideia do resto do sistema: a view pergunta, este arquivo decide, e o
padrao e NEGAR. As listas abaixo dizem quem PODE; quem nao esta nelas, nao
pode, e nao existe lista de quem nao pode.
"""

from datetime import date

from django.db.models import Q

from relatorios.models import Perfil
from relatorios.permissions import obter_perfil, turmas_visiveis

from .models import Recado

# Quem manda recado para a propria turma.
PERFIS_QUE_PUBLICAM = (
    Perfil.Tipo.PROFESSOR,
    Perfil.Tipo.COORDENADOR,
    Perfil.Tipo.DIRETOR,
)

# Recado para a ESCOLA INTEIRA e outra coisa: fala em nome da instituicao,
# entao fica com a gestao. O professor manda para a turma dele.
PERFIS_QUE_FALAM_PELA_ESCOLA = (
    Perfil.Tipo.COORDENADOR,
    Perfil.Tipo.DIRETOR,
)


def pode_publicar_recado(user):
    perfil = obter_perfil(user)
    return (
        user.is_active
        and perfil is not None
        and perfil.tipo in PERFIS_QUE_PUBLICAM
    )


def pode_publicar_recado_geral(user):
    """Recado sem turma, dirigido a escola inteira."""
    perfil = obter_perfil(user)
    return (
        user.is_active
        and perfil is not None
        and perfil.tipo in PERFIS_QUE_FALAM_PELA_ESCOLA
    )


def eh_equipe_da_escola(user):
    """Professor, coordenacao e direcao.

    Decide quem enxerga tambem os recados ja encerrados: a equipe precisa
    saber o que ja foi publicado; a familia so precisa do que esta no ar.
    """
    perfil = obter_perfil(user)
    return (
        user.is_active
        and perfil is not None
        and perfil.tipo in PERFIS_QUE_PUBLICAM
    )


def recados_visiveis(user):
    """Recados das turmas que a pessoa enxerga, mais os gerais.

    Devolve sempre um queryset, nunca None, para que a view possa continuar
    filtrando sem precisar testar.
    """
    perfil = obter_perfil(user)

    if perfil is None or not user.is_active:
        return Recado.objects.none()

    # turma__isnull=True traz os recados da escola inteira, que valem para
    # todo mundo que tem conta.
    da_turma_ou_geral = (
        Q(turma__in=turmas_visiveis(user)) | Q(turma__isnull=True)
    )
    visiveis = Recado.objects.filter(da_turma_ou_geral)

    if not eh_equipe_da_escola(user):
        no_ar = Q(exibir_ate__isnull=True) | Q(exibir_ate__gte=date.today())
        visiveis = visiveis.filter(no_ar)

    return visiveis.select_related('turma', 'autor')
