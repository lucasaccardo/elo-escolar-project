"""Como os arquivos estáticos são publicados em produção.

O Django, ao preparar os arquivos estáticos, acrescenta um resumo do
conteúdo ao nome de cada um (estilo.a1b2c3.css) e depois varre os arquivos
reescrevendo as referências internas para apontar aos nomes novos. Entre as
referências que ele persegue está o comentário `sourceMappingURL`, que
biblioteca alguma publica junto: é um arquivo de depuração, usado por quem
desenvolve a biblioteca, e não é distribuído com ela.

O Chart.js, que o projeto serve a partir do próprio servidor para não
depender de rede externa, traz esse comentário. Com a regra padrão, a
publicação falha porque o arquivo de mapa não existe — e falha inteira, não
só naquele arquivo.

A classe abaixo remove apenas essa regra. Tudo o mais continua igual: o
resumo no nome, a compactação e a reescrita das referências que de fato
existem.
"""

# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Como os arquivos estaticos sao servidos em
#                      producao, com resumo do conteudo no nome de cada
#                      arquivo.
#   REQUISITOS.......: RNF08
#   PROCURE POR......: estaticos, cache, manifesto, WhiteNoise,
#                      sourceMappingURL
# ----------------------------------------------------------------------

import re

from whitenoise.storage import CompressedManifestStaticFilesStorage


def _texto_da_regra(regra):
    """Cada regra é uma expressão regular ou uma tupla que começa com uma."""
    return regra if isinstance(regra, str) else regra[0]


def _sem_mapa_de_codigo(padroes):
    limpos = []
    for extensao, regras in padroes:
        mantidas = tuple(
            regra for regra in regras
            if 'sourceMappingURL' not in _texto_da_regra(regra)
        )
        if mantidas:
            limpos.append((extensao, mantidas))
    return tuple(limpos)


class ArquivosEstaticos(CompressedManifestStaticFilesStorage):

    patterns = _sem_mapa_de_codigo(
        CompressedManifestStaticFilesStorage.patterns
    )

    # Mantido para deixar explícito que a checagem continua rigorosa: uma
    # referência a arquivo inexistente que não seja mapa de código ainda
    # derruba a publicação, que é o comportamento desejado.
    manifest_strict = True


assert not any(
    'sourceMappingURL' in _texto_da_regra(regra)
    for _, regras in ArquivosEstaticos.patterns
    for regra in regras
), 'a regra de mapa de código continuou ativa'

assert any(
    re.search(r'url\\\(', _texto_da_regra(regra))
    for _, regras in ArquivosEstaticos.patterns
    for regra in regras
), 'a reescrita de url() em CSS foi removida por engano'
