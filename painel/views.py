from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from relatorios.permissions import eh_responsavel

from .services import (
    indicadores,
    relatorios_por_semana,
    relatorios_por_turma,
)


@login_required
def painel(request):
    # Os dados dos graficos vao para o template como dicionario mesmo, e
    # quem os transforma em JSON e o filtro json_script do proprio Django.
    # Ele escapa o conteudo corretamente dentro da pagina, o que evita o
    # risco de alguem conseguir injetar script por um nome de turma.
    por_turma = relatorios_por_turma(request.user)
    por_semana = relatorios_por_semana(request.user)

    return render(request, 'painel/painel.html', {
        'indicadores': indicadores(request.user),
        'grafico_turmas': por_turma,
        'grafico_semanas': por_semana,
        'tem_dado_por_turma': bool(por_turma['valores']),
        'eh_familia': eh_responsavel(request.user),
    })
