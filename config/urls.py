# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Tabela de enderecos do sistema: diz qual
#                      endereco chama qual tela.
#   REQUISITOS.......: RF01, RF13
#   PROCURE POR......: urlpatterns, rota, endereco, login,
#                      password_reset, include
# ----------------------------------------------------------------------

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

from acessos.forms import LoginForm
from acessos import views_senha

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'contas/login/',
        auth_views.LoginView.as_view(
            redirect_authenticated_user=True,
            authentication_form=LoginForm,
        ),
        name='login',
    ),
    # As quatro rotas abaixo repetem os caminhos do pacote de autenticacao
    # do Django e vem ANTES do include. O resolvedor usa a primeira que
    # casa, entao sao estas que atendem; o reverse devolve o mesmo
    # endereco, porque o caminho e identico. E a forma de trocar as telas
    # de redefinicao de senha sem abrir mao do resto do pacote.
    path(
        'contas/password_reset/',
        views_senha.PedirRedefinicaoView.as_view(),
        name='password_reset',
    ),
    path(
        'contas/password_reset/done/',
        views_senha.RedefinicaoEnviadaView.as_view(),
        name='password_reset_done',
    ),
    path(
        'contas/reset/<uidb64>/<token>/',
        views_senha.ConfirmarRedefinicaoView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'contas/reset/done/',
        views_senha.RedefinicaoConcluidaView.as_view(),
        name='password_reset_complete',
    ),
    path('contas/', include('django.contrib.auth.urls')),
    path('acessos/', include('acessos.urls')),
    path('recados/', include('recados.urls')),
    path('painel/', include('painel.urls')),
    path('solicitacoes/', include('solicitacoes.urls')),
    path('', include('relatorios.urls')),
]
