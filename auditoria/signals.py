# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Liga os avisos de entrada e de erro de entrada
#                      do Django ao log de auditoria, sem precisar
#                      alterar a tela de login.
#   REQUISITOS.......: RF07, RF01
#   PROCURE POR......: signals, user_logged_in, user_login_failed,
#                      LOGIN, LOGIN_FALHA
# ----------------------------------------------------------------------

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .models import Evento
from .services import registrar


@receiver(user_logged_in)
def ao_entrar(sender, request, user, **kwargs):
    registrar(Evento.Acao.LOGIN, usuario=user)


@receiver(user_login_failed)
def ao_falhar_login(sender, credentials, **kwargs):
    # O Django já troca a senha por asteriscos antes de avisar.
    registrar(
        Evento.Acao.LOGIN_FALHA,
        usuario_informado=credentials.get('username', ''),
    )