from django.shortcuts import redirect
from django.urls import reverse

from .permissions import aceitou_termos


class ExigirAceiteTermos:
    """Nenhuma tela protegida abre sem o aceite da versao vigente dos Termos.

    A conferencia fica aqui, no meio do caminho de TODA requisicao, e nao
    em cada view. Assim uma tela nova nasce protegida por padrao: ninguem
    precisa lembrar de colocar o decorator nela.
    """

    # Unicas rotas que continuam abertas para quem ainda nao aceitou.
    # Sem elas a pessoa ficaria presa: nao conseguiria ler o que vai
    # aceitar, nem aceitar, nem sair do sistema.
    LIBERADAS = {
        'aceitar_termos',
        'termos',
        'privacidade',
        'login',
        'logout',
        'inicio',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Visitante nao logado nao tem o que aceitar ainda.
        if not request.user.is_authenticated:
            return None

        rota = getattr(request.resolver_match, 'url_name', None)
        if rota in self.LIBERADAS:
            return None

        if aceitou_termos(request.user):
            return None

        # Guarda para onde a pessoa queria ir, para devolve-la depois.
        destino = reverse('aceitar_termos')
        return redirect(f'{destino}?next={request.path}')