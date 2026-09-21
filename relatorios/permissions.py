from .models import Perfil, Turma  # Traz Perfil e Turma do models.py


# Lista fixa com os 3 tipos que podem publicar.
# É aqui que mora o "negue por padrão": quem não está nessa lista, não publica.
PERFIS_QUE_PUBLICAM = (
    Perfil.Tipo.PROFESSOR,
    Perfil.Tipo.COORDENADOR,
    Perfil.Tipo.DIRETOR,
)


# Quem supervisiona enxerga todas as turmas.
PERFIS_QUE_VEEM_TODAS = (
    Perfil.Tipo.COORDENADOR,
    Perfil.Tipo.DIRETOR,
)


def obter_perfil(user):
    return getattr(user, 'perfil', None)


def eh_responsavel(user):
    perfil = obter_perfil(user)
    return perfil is not None and perfil.tipo == Perfil.Tipo.RESPONSAVEL


def pode_publicar_relatorio(user):
    perfil = obter_perfil(user)
    return (
        user.is_active
        and perfil is not None
        and perfil.tipo in PERFIS_QUE_PUBLICAM
    )


def turmas_visiveis(user):
    perfil = obter_perfil(user)

    if perfil is None or not user.is_active:
        return Turma.objects.none()

    if perfil.tipo in PERFIS_QUE_VEEM_TODAS:
        return Turma.objects.all()

    if perfil.tipo == Perfil.Tipo.PROFESSOR:
        return Turma.objects.filter(professor=user)

    if perfil.tipo == Perfil.Tipo.RESPONSAVEL:
        turmas_dos_filhos = perfil.alunos.values_list('turma_id', flat=True)
        return Turma.objects.filter(id__in=turmas_dos_filhos)

    return Turma.objects.none()