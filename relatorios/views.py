from django.shortcuts import render, redirect
from .models import RelatorioDiario, Turma
from .forms import RelatorioDiarioForm

def lista_relatorios(request):
    # A ordenação padrão (-data_aula) já é garantida pelo class Meta do model
    relatorios = RelatorioDiario.objects.all()
    
    # Busca todas as turmas e ordena em ordem alfabética para o seletor
    turmas = Turma.objects.all().order_by('nome')
    
    # Lê o parâmetro 'turma' da URL (ex: ?turma=1)
    turma_id = request.GET.get('turma')
    
    # Se vier uma turma selecionada, aplica o filtro na consulta
    if turma_id:
        relatorios = relatorios.filter(turma_id=turma_id)
    
    # Renderiza o template passando o contexto completo
    return render(request, 'relatorios/lista_relatorios.html', {
        'relatorios': relatorios,
        'turmas': turmas,
        'turma_selecionada': turma_id,
    })

def cadastrar_relatorio(request):
    if request.method == 'POST':
        form = RelatorioDiarioForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_relatorios')
    else:
        form = RelatorioDiarioForm()

    return render(request, 'relatorios/cadastrar_relatorio.html', {'form': form})