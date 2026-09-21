from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import CadastroResponsavelForm
from .models import SolicitacaoAcesso

User = get_user_model()


def cadastro_responsavel(request):
    if request.method == 'POST':
        form = CadastroResponsavelForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            # Ou grava as duas coisas, ou não grava nenhuma.
            with transaction.atomic():
                usuario = User.objects.create_user(
                    username=dados['email'],
                    email=dados['email'],
                    password=dados['senha'],
                    first_name=dados['nome'],
                    last_name=dados['sobrenome'],
                    is_active=False,
                )
                SolicitacaoAcesso.objects.create(
                    usuario=usuario,
                    aluno=form.aluno,
                    aceite_termos_em=timezone.now(),
                )
            return redirect('cadastro_enviado')
    else:
        form = CadastroResponsavelForm()

    return render(request, 'acessos/cadastro.html', {'form': form})


def cadastro_enviado(request):
    return render(request, 'acessos/cadastro_enviado.html')