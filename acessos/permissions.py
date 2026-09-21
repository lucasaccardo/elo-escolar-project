from relatorios.models import Perfil
from relatorios.permissions import obter_perfil, turmas_visiveis

from .models import SolicitacaoAcesso

# Quem pode analisar pedidos de acesso de responsáveis.
# Negue por padrão: quem não está nesta lista, não analisa.
PERFIS_QUE_APROVAM = (
    Perfil.Tipo.PROFESSOR,
    Perfil.Tipo.COORDENADOR,
    Perfil.Tipo.DIRETOR,
)


def pode_aprovar_acessos(user):
    perfil = obter_perfil(user)
    return (
        user.is_active
        and perfil is not None
        and perfil.tipo in PERFIS_QUE_APROVAM
    )


def solicitacoes_que_pode_analisar(user):
    # Reaproveita a regra das turmas: o professor só vê pedidos das
    # turmas dele; coordenação e direção veem todos.
    if not pode_aprovar_acessos(user):
        return SolicitacaoAcesso.objects.none()
    return SolicitacaoAcesso.objects.filter(
        aluno__turma__in=turmas_visiveis(user)
    )