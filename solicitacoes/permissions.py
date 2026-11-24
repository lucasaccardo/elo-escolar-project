"""Quem abre, quem enxerga, quem responde e quem encerra uma solicitação.

Mesmo desenho do resto do sistema: a view pergunta, este arquivo decide, e o
padrão é NEGAR. As listas dizem quem PODE; quem não está nelas, não pode.
"""

# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Quem abre, quem responde e quem encerra
#                      solicitacao. Aqui aparece a permissao de OBJETO:
#                      nao basta poder agir, tem de poder agir sobre
#                      aquele registro.
#   REQUISITOS.......: RF10
#   PROCURE POR......: permissao de objeto, autorizacao,
#                      pode_abrir_solicitacao, pode_responder,
#                      pode_encerrar, foro particular
# ----------------------------------------------------------------------

from relatorios.models import Perfil
from relatorios.permissions import (
    eh_responsavel,
    obter_perfil,
    turmas_visiveis,
)

from .models import Solicitacao

# Quem responde solicitação. O professor responde as das turmas em que
# leciona; a gestão responde qualquer uma. O recorte por turma é feito na
# consulta, reaproveitando turmas_visiveis.
PERFIS_QUE_RESPONDEM = (
    Perfil.Tipo.PROFESSOR,
    Perfil.Tipo.COORDENADOR,
    Perfil.Tipo.DIRETOR,
)


def pode_abrir_solicitacao(user):
    """Só a família abre solicitação.

    A equipe escolar tem o relatório e o mural de recados para falar com as
    famílias; a solicitação existe para o caminho inverso.
    """
    return user.is_active and eh_responsavel(user)


def pode_responder_solicitacoes(user):
    perfil = obter_perfil(user)
    return (
        user.is_active
        and perfil is not None
        and perfil.tipo in PERFIS_QUE_RESPONDEM
    )


def solicitacoes_visiveis(user):
    """O que cada perfil enxerga.

    Devolve sempre um queryset, nunca None, para que a view possa continuar
    filtrando sem precisar testar.
    """
    perfil = obter_perfil(user)

    if perfil is None or not user.is_active:
        return Solicitacao.objects.none()

    if eh_responsavel(user):
        # A família vê apenas o que ela própria abriu. Não basta filtrar
        # pelos filhos: duas pessoas podem ser responsáveis pela mesma
        # criança, e o que uma escreveu à escola não é da outra.
        visiveis = Solicitacao.objects.filter(autor=user)
    elif pode_responder_solicitacoes(user):
        # Mesma regra de visibilidade das demais telas: o professor vê as
        # solicitações dos alunos das turmas em que leciona.
        visiveis = Solicitacao.objects.filter(
            aluno__turma__in=turmas_visiveis(user),
        )
    else:
        return Solicitacao.objects.none()

    return visiveis.select_related('aluno', 'aluno__turma', 'autor')


def pode_responder(user, solicitacao):
    """Permissão de objeto: pode responder ESTA solicitação?

    Depende de duas coisas: do perfil e de a solicitação pertencer a uma
    turma que a pessoa enxerga. Uma solicitação já encerrada não recebe
    resposta nova.
    """
    if not pode_responder_solicitacoes(user):
        return False

    if solicitacao.situacao == Solicitacao.Situacao.ENCERRADA:
        return False

    return solicitacoes_visiveis(user).filter(pk=solicitacao.pk).exists()


def pode_encerrar(user, solicitacao):
    """Quem encerra é quem abriu, e só depois de receber resposta.

    Encerrar antes da resposta esconderia da escola um pedido que ela ainda
    não viu; depois da resposta, é a família dizendo que está resolvido.
    """
    return (
        user.is_active
        and solicitacao.autor_id == user.id
        and solicitacao.situacao == Solicitacao.Situacao.RESPONDIDA
    )
