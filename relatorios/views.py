from django.shortcuts import render
from .models import RelatorioDiario

def lista_relatorios(request):
    # Por enquanto, busca todos os relatórios do banco de dados. 
    relatorios = RelatorioDiario.objects.all()
    
    # Renderiza o template passando o dicionário de contexto
    return render(request, 'relatorios/lista_relatorios.html', {'relatorios': relatorios})