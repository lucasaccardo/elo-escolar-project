from django.shortcuts import render, redirect
from .models import RelatorioDiario
from.forms import RelatorioDiarioForm


def lista_relatorios(request):
    # Por enquanto, busca todos os relatórios do banco de dados. 
    relatorios = RelatorioDiario.objects.all()
    
    # Renderiza o template passando o dicionário de contexto
    return render(request, 'relatorios/lista_relatorios.html', {'relatorios': relatorios})

def cadastrar_relatorio(request):
    if request.method == 'POST':
        form = RelatorioDiarioForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_relatorios')
    else:
        form = RelatorioDiarioForm()

    return render(request, 'relatorios/cadastrar_relatorio.html', {'form': form})