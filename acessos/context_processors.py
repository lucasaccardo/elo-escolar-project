from relatorios.permissions import obter_perfil, pode_publicar_relatorio

from .models import SolicitacaoAcesso
from .permissions import pode_aprovar_acessos, solicitacoes_que_pode_analisar


def menu_acessos(request):
    # Monta o menu lateral de TODAS as telas. Quem decide o que aparece
    # continua sendo o permissions.py: aqui só perguntamos.
    usuario = request.user
    if not usuario.is_authenticated:
        return {}

    perfil = obter_perfil(usuario)

    dados = {
        'perfil_tipo': perfil.get_tipo_display() if perfil else '',
        'pode_publicar': pode_publicar_relatorio(usuario),
        'mostrar_pedidos': pode_aprovar_acessos(usuario),
        'pedidos_pendentes': 0,
    }

    if dados['mostrar_pedidos']:
        dados['pedidos_pendentes'] = solicitacoes_que_pode_analisar(usuario).filter(
            status=SolicitacaoAcesso.Status.PENDENTE
        ).count()

    return dados