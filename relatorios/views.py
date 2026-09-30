from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from auditoria.models import Evento
from auditoria.services import registrar

from .forms import RelatorioDiarioForm
from .models import RelatorioDiario
from .permissions import pode_publicar_relatorio, turmas_visiveis




def pagina_inicial(request):
    # Vitrine publica. Quem ja esta logado nao precisa dela: vai direto ao sistema.
    if request.user.is_authenticated:
        return redirect('lista_relatorios')
    return render(request, 'relatorios/inicio.html')




@login_required
def lista_relatorios(request):
    turmas = turmas_visiveis(request.user).order_by('nome')
    relatorios = RelatorioDiario.objects.filter(turma__in=turmas)

    turma_id = request.GET.get('turma')
    if turma_id:
        relatorios = relatorios.filter(turma_id=turma_id)

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