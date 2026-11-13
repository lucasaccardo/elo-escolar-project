import os
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from auditoria.models import Evento
from auditoria.services import registrar
from relatorios.permissions import turmas_visiveis

from .forms import RecadoForm
from .permissions import (
    pode_publicar_recado,
    pode_publicar_recado_geral,
    recados_visiveis,
)


@login_required
def lista_recados(request):
    recados = recados_visiveis(request.user)

    return render(request, 'recados/lista_recados.html', {
        'recados': recados,
        'pode_publicar_recado': pode_publicar_recado(request.user),
    })


@login_required
def cadastrar_recado(request):
    if not pode_publicar_recado(request.user):
        raise PermissionDenied

    fala_pela_escola = pode_publicar_recado_geral(request.user)

    if request.method == 'POST':
        form = RecadoForm(
            request.POST, pode_falar_pela_escola=fala_pela_escola,
        )
    else:
        form = RecadoForm(pode_falar_pela_escola=fala_pela_escola)

    # Mesma protecao do relatorio diario: a lista de turmas do formulario e
    # restrita ao que a pessoa enxerga, entao nao adianta forjar um id.
    form.fields['turma'].queryset = turmas_visiveis(request.user)

    if request.method == 'POST' and form.is_valid():
        recado = form.save(commit=False)
        recado.autor = request.user
        recado.save()
        registrar(
            Evento.Acao.RECADO_PUBLICADO,
            usuario=request.user,
            detalhe=f'{recado}',
        )
        return redirect('lista_recados')

    return render(request, 'recados/cadastrar_recado.html', {
        'form': form,
        'pode_falar_pela_escola': fala_pela_escola,
    })
