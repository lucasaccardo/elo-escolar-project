# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Tela de consulta do log de auditoria, com filtro
#                      por acao, busca por pessoa e paginacao.
#   REQUISITOS.......: RF07
#   PROCURE POR......: log de auditoria, lista_eventos, filtro, busca,
#                      paginacao, somente leitura, 403
# ----------------------------------------------------------------------

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render

from .models import Evento
from .permissions import pode_consultar_log

# Quantos eventos por pagina. O log cresce sem parar, entao a tela nunca
# carrega tudo: sem isto, uma escola com meses de uso travaria o
# navegador na primeira abertura.
POR_PAGINA = 50


@login_required
def lista_eventos(request):
    # A tela pergunta, o permissions.py decide. Quem nao pode consultar
    # recebe 403 - e nao uma lista vazia, que esconderia o motivo.
    if not pode_consultar_log(request.user):
        raise PermissionDenied

    eventos = Evento.objects.select_related('usuario')

    # Filtro por tipo de acao. So aceita valor que exista entre as
    # opcoes do modelo; qualquer outra coisa e ignorada, em vez de ir
    # parar na consulta ao banco.
    acao = request.GET.get('acao', '')
    if acao in Evento.Acao.values:
        eventos = eventos.filter(acao=acao)
    else:
        acao = ''

    # Busca por quem fez. Procura nos dois campos porque a acao pode ter
    # sido de alguem com conta (usuario) ou de alguem que apenas digitou
    # um endereco na tela de entrada (usuario_informado).
    procura = request.GET.get('q', '').strip()
    if procura:
        from django.db.models import Q
        eventos = eventos.filter(
            Q(usuario__username__icontains=procura)
            | Q(usuario__first_name__icontains=procura)
            | Q(usuario__last_name__icontains=procura)
            | Q(usuario_informado__icontains=procura)
        )

    paginas = Paginator(eventos, POR_PAGINA)
    pagina = paginas.get_page(request.GET.get('pagina'))

    return render(request, 'auditoria/log.html', {
        'pagina': pagina,
        'acoes': Evento.Acao.choices,
        'acao_escolhida': acao,
        'procura': procura,
        'total': paginas.count,
    })
