from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import RelatorioDiario, Turma, Perfil
from .forms import RelatorioDiarioForm


@login_required
def lista_relatorios(request):
    # Pega o perfil de quem esta logado (pode nao existir)
    perfil = getattr(request.user, 'perfil', None)
    eh_responsavel = perfil is not None and perfil.tipo == Perfil.Tipo.RESPONSAVEL

    # A ordenacao padrao (-data_aula) ja vem do class Meta do model
    relatorios = RelatorioDiario.objects.all()
    turmas = Turma.objects.all().order_by('nome')

    # O responsavel so enxerga as turmas dos filhos dele
    if eh_responsavel:
        turmas_dos_filhos = perfil.alunos.values_list('turma_id', flat=True)
        relatorios = relatorios.filter(turma_id__in=turmas_dos_filhos)
        turmas = turmas.filter(id__in=turmas_dos_filhos)

    # Filtro opcional escolhido na tela
    turma_id = request.GET.get('turma')
    if turma_id:
        relatorios = relatorios.filter(turma_id=turma_id)

    return render(request, 'relatorios/lista_relatorios.html', {
        'relatorios': relatorios,
        'turmas': turmas,
        'turma_selecionada': turma_id,
        'pode_publicar': not eh_responsavel,
    })


@login_required
def cadastrar_relatorio(request):
    # Responsavel nao publica relatorio
    perfil = getattr(request.user, 'perfil', None)
    if perfil is None or perfil.tipo == Perfil.Tipo.RESPONSAVEL:
        raise PermissionDenied

    if request.method == 'POST':
        form = RelatorioDiarioForm(request.POST)
        if form.is_valid():
            # O formulario nao traz o autor, ele vem da sessao autenticada
            relatorio = form.save(commit=False)
            relatorio.autor = request.user
            relatorio.save()
            return redirect('lista_relatorios')
    else:
        form = RelatorioDiarioForm()

    return render(request, 'relatorios/cadastrar_relatorio.html', {'form': form})