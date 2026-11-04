from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from auditoria.models import Evento
from auditoria.services import registrar

from .forms import RelatorioDiarioForm
from .models import RelatorioDiario
from .permissions import (
    pode_editar_relatorio,
    pode_excluir_relatorio,
    pode_publicar_relatorio,
    turmas_visiveis,
)




def pagina_inicial(request):
    # Vitrine publica. Quem ja esta logado nao precisa dela: vai direto ao sistema.
    if request.user.is_authenticated:
        return redirect('lista_relatorios')
    return render(request, 'relatorios/inicio.html')




@login_required
def lista_relatorios(request):
    turmas = turmas_visiveis(request.user).order_by('nome')

    # excluido=False e a exclusao logica funcionando: o registro continua no
    # banco, so nao entra mais na consulta.
    # select_related traz turma e autor na MESMA consulta. Sem ele, o template
    # faria uma consulta por relatorio ao escrever o nome do autor: e o
    # problema
    # classico conhecido como N+1.
    relatorios = (
        RelatorioDiario.objects
        .filter(turma__in=turmas, excluido=False)
        .select_related('turma', 'autor')
    )

    turma_id = request.GET.get('turma')
    if turma_id:
        relatorios = relatorios.filter(turma_id=turma_id)

    # O template nao consegue chamar funcao com argumento, entao a resposta de
    # "esta pessoa pode mexer NESTE relatorio" e calculada aqui e pendurada em
    # cada objeto. A regra continua em permissions.py: a view pergunta,
    # ela decide.
    relatorios = list(relatorios)
    for relatorio in relatorios:
        relatorio.pode_editar = pode_editar_relatorio(request.user, relatorio)
        relatorio.pode_excluir = pode_excluir_relatorio(
            request.user, relatorio,
        )

    return render(request, 'relatorios/lista_relatorios.html', {
        'relatorios': relatorios,
        'turmas': turmas,
        'turma_selecionada': turma_id,
        'pode_publicar': pode_publicar_relatorio(request.user),
    })


@login_required
def cadastrar_relatorio(request):
    if not pode_publicar_relatorio(request.user):
        raise PermissionDenied

    if request.method == 'POST':
        form = RelatorioDiarioForm(request.POST)
    else:
        form = RelatorioDiarioForm()

    form.fields['turma'].queryset = turmas_visiveis(request.user)

    if request.method == 'POST' and form.is_valid():
        relatorio = form.save(commit=False)
        relatorio.autor = request.user
        relatorio.save()
        registrar(
            Evento.Acao.RELATORIO_PUBLICADO,
            usuario=request.user,
            detalhe=f'{relatorio.turma} / aula de {relatorio.data_aula}',
        )
        return redirect('lista_relatorios')

    return render(request, 'relatorios/cadastrar_relatorio.html', {'form': form})


@login_required
def editar_relatorio(request, pk):
    # excluido=False dentro do get_object_or_404: um relatorio ja retirado do
    # ar responde 404, e nao 403. A diferenca importa - 403 diria "existe, mas
    # voce nao pode", e nao e isso.
    relatorio = get_object_or_404(RelatorioDiario, pk=pk, excluido=False)

    if not pode_editar_relatorio(request.user, relatorio):
        raise PermissionDenied

    if request.method == 'POST':
        form = RelatorioDiarioForm(request.POST, instance=relatorio)
    else:
        form = RelatorioDiarioForm(instance=relatorio)

    form.fields['turma'].queryset = turmas_visiveis(request.user)

    if request.method == 'POST' and form.is_valid():
        relatorio = form.save(commit=False)
        relatorio.editado_em = timezone.now()
        relatorio.editado_por = request.user
        relatorio.save()
        registrar(
            Evento.Acao.RELATORIO_EDITADO,
            usuario=request.user,
            detalhe=f'{relatorio.turma} / aula de {relatorio.data_aula}',
        )
        return redirect('lista_relatorios')

    return render(request, 'relatorios/editar_relatorio.html', {
        'form': form,
        'relatorio': relatorio,
    })


@login_required
@require_POST
def excluir_relatorio(request, pk):
    # require_POST: excluir muda o estado do sistema, entao nao pode acontecer
    # por um simples endereco digitado na barra do navegador. Um GET aqui
    # responde 405.
    relatorio = get_object_or_404(RelatorioDiario, pk=pk, excluido=False)

    if not pode_excluir_relatorio(request.user, relatorio):
        raise PermissionDenied

    relatorio.excluido = True
    relatorio.excluido_em = timezone.now()
    relatorio.excluido_por = request.user
    # update_fields escreve SO estas tres colunas. Nada mais do relatorio pode
    # ser alterado sem querer por este caminho.
    relatorio.save(update_fields=['excluido', 'excluido_em', 'excluido_por'])

    registrar(
        Evento.Acao.RELATORIO_EXCLUIDO,
        usuario=request.user,
        detalhe=f'{relatorio.turma} / aula de {relatorio.data_aula}',
    )
    return redirect('lista_relatorios')
