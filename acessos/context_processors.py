from .models import SolicitacaoAcesso
from .permissions import pode_aprovar_acessos, solicitacoes_que_pode_analisar


def menu_acessos(request):
    # Entrega para TODAS as telas se o menu "Pedidos de acesso" aparece
    # e quantos pedidos estão esperando.
    usuario = request.user
    if not usuario.is_authenticated or not pode_aprovar_acessos(usuario):
        return {}

    pendentes = solicitacoes_que_pode_analisar(usuario).filter(
        status=SolicitacaoAcesso.Status.PENDENTE
    )
    return {
        'mostrar_pedidos': True,
        'pedidos_pendentes': pendentes.count(),
    }