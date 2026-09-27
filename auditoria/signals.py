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