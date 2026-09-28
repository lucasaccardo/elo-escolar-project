import json
import urllib.error
import urllib.request

from decouple import config

# Endereço da API de e-mail transacional do Brevo.
API_URL = 'https://api.brevo.com/v3/smtp/email'


def enviar_email(destinatario, nome, assunto, texto):
    """Chama a API externa e devolve (deu_certo, detalhe)."""
    chave = config('BREVO_API_KEY', default='')
    remetente = config('EMAIL_REMETENTE', default='')

    if not chave or not remetente:
        return False, 'servico de e-mail nao configurado'

    corpo = json.dumps({
        'sender': {'name': 'Elo Escolar', 'email': remetente},
        'to': [{'email': destinatario, 'name': nome}],
        'subject': assunto,
        'textContent': texto,
    }).encode('utf-8')

    requisicao = urllib.request.Request(
        API_URL,
        data=corpo,
        headers={
            'api-key': chave,
            'content-type': 'application/json',
            'accept': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(requisicao, timeout=10) as resposta:
            return True, f'HTTP {resposta.status}'
    except urllib.error.HTTPError as erro:
        return False, f'HTTP {erro.code}'
    except urllib.error.URLError as erro:
        return False, f'sem conexao: {erro.reason}'