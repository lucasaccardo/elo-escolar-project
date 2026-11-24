# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Informacoes que toda tela precisa, como o perfil
#                      de quem esta conectado e os contadores do menu.
#   REQUISITOS.......: RF06
#   PROCURE POR......: context processor, menu, perfil, contador
# ----------------------------------------------------------------------

from recados.permissions import pode_publicar_recado
from solicitacoes.permissions import (
    pode_abrir_solicitacao,
    pode_responder_solicitacoes,
)
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
        'pode_publicar_recado': pode_publicar_recado(usuario),
        'pode_abrir_solicitacao': pode_abrir_solicitacao(usuario),
        'mostrar_solicitacoes': (
            pode_abrir_solicitacao(usuario)
            or pode_responder_solicitacoes(usuario)
        ),
        'mostrar_pedidos': pode_aprovar_acessos(usuario),
        'pedidos_pendentes': 0,
    }

    # Contador do menu: a equipe precisa ver quantas solicitacoes ainda
    # esperam resposta; a familia, quantas ja foram respondidas e ela ainda
    # nao encerrou. Cada perfil conta a sua propria novidade.
    dados['solicitacoes_abertas'] = 0
    if dados['mostrar_solicitacoes']:
        from solicitacoes.models import Solicitacao
        from solicitacoes.permissions import solicitacoes_visiveis
        alvo = (
            Solicitacao.Situacao.RESPONDIDA
            if dados['pode_abrir_solicitacao']
            else Solicitacao.Situacao.ABERTA
        )
        dados['solicitacoes_abertas'] = solicitacoes_visiveis(
            usuario,
        ).filter(situacao=alvo).count()

    if dados['mostrar_pedidos']:
        dados['pedidos_pendentes'] = solicitacoes_que_pode_analisar(usuario).filter(
            status=SolicitacaoAcesso.Status.PENDENTE
        ).count()

    return dados
