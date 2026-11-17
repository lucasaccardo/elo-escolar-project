#!/usr/bin/env bash
# Roteiro de publicacao do Elo Escolar no Render.
#
# O Render executa este arquivo a cada envio para a branch principal. O
# `set -o errexit` faz a publicacao parar no primeiro erro, em vez de
# seguir adiante e colocar no ar uma versao quebrada.
set -o errexit

pip install -r requirements.txt

# Junta os arquivos estaticos num lugar so, com o resumo do conteudo no
# nome de cada um, para o WhiteNoise servir.
python manage.py collectstatic --no-input

# Aplica as migracoes pendentes. O plano gratuito nao oferece terminal no
# servidor, entao este e o unico momento em que isso pode acontecer.
python manage.py migrate

# Povoa o banco com os dados de demonstracao apenas quando a variavel
# CRIAR_DEMO estiver ligada. A senha vem de DEMO_SENHA, nunca do codigo.
if [ "$CRIAR_DEMO" = "1" ]; then
  python manage.py criar_demo
fi
