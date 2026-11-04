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


# Quem corrige QUALQUER relatorio, mesmo os que nao escreveu.
# O professor nao esta nesta lista de proposito: ele corrige so o proprio,
# e isso e tratado dentro da funcao, porque depende do relatorio e nao so
# do perfil.
PERFIS_QUE_EDITAM_QUALQUER = (
    Perfil.Tipo.COORDENADOR,
    Perfil.Tipo.DIRETOR,
)


# Excluir e mais destrutivo do que editar: tira da vista das familias algo
# que elas ja podiam ler. Por isso fica so com a gestao.
PERFIS_QUE_EXCLUEM = (
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


def pode_editar_relatorio(user, relatorio):
    """Quem pode corrigir um relatorio JA publicado.

    Repare que esta funcao recebe DOIS argumentos, diferente de
    pode_publicar_relatorio, que recebe so o usuario. E porque a regra nao
    depende apenas de quem a pessoa e: depende tambem de qual relatorio ela
    esta tentando mexer. O professor corrige o proprio; a gestao corrige
    qualquer um.
    """
    perfil = obter_perfil(user)

    if perfil is None or not user.is_active:
        return False

    # Relatorio excluido nao se edita. Primeiro se restaura.
    if relatorio.excluido:
        return False

    if perfil.tipo in PERFIS_QUE_EDITAM_QUALQUER:
        return True

    if perfil.tipo == Perfil.Tipo.PROFESSOR:
        # Comparar os ids evita ir ao banco buscar o objeto do autor.
        # O "is not None" protege o caso de um relatorio ainda sem autor
        # gravado: sem ele, None == None liberaria para qualquer um.
        return (
            relatorio.autor_id is not None
            and relatorio.autor_id == user.id
        )

    return False


def pode_excluir_relatorio(user, relatorio):
    """Quem pode retirar um relatorio da vista das familias.

    Decisao de projeto: so coordenacao e direcao. O professor corrige o que
    escreveu, mas retirar do ar um conteudo que as familias ja leram e uma
    decisao de gestao.
    """
    perfil = obter_perfil(user)

    if perfil is None or not user.is_active:
        return False

    # Ja esta excluido: nao ha o que excluir de novo.
    if relatorio.excluido:
        return False

    return perfil.tipo in PERFIS_QUE_EXCLUEM


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