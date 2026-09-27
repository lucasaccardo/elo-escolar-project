from .models import Evento


def registrar(acao, usuario=None, usuario_informado='', detalhe=''):
    # Uma função só para gravar no log: uma informação, um lugar.
    # Nunca passar senha nem token para cá.
    if usuario is not None and not usuario.is_authenticated:
        usuario = None

    return Evento.objects.create(
        acao=acao,
        usuario=usuario,
        usuario_informado=usuario_informado[:150],
        detalhe=detalhe[:255],
    )