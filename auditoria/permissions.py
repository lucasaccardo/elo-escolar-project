# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Quem pode consultar o log de auditoria.
#   REQUISITOS.......: RF07
#   PROCURE POR......: permissao, autorizacao, negar por padrao,
#                      pode_consultar_log, auditoria
# ----------------------------------------------------------------------

from relatorios.models import Perfil
from relatorios.permissions import obter_perfil

# O log mostra o que todo mundo fez, inclusive os colegas. Por isso a
# consulta e privativa da gestao: o professor responde pelo proprio
# trabalho, a coordenacao e a direcao respondem pela escola.
#
# Negue por padrao: quem nao esta nesta lista, nao consulta.
PERFIS_QUE_CONSULTAM_O_LOG = (
    Perfil.Tipo.COORDENADOR,
    Perfil.Tipo.DIRETOR,
)


def pode_consultar_log(user):
    perfil = obter_perfil(user)
    return (
        user.is_authenticated
        and user.is_active
        and perfil is not None
        and perfil.tipo in PERFIS_QUE_CONSULTAM_O_LOG
    )
