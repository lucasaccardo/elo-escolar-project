from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from relatorios.models import Perfil

from .forms import CadastroResponsavelForm
from .models import SolicitacaoAcesso
from .permissions import pode_aprovar_acessos, solicitacoes_que_pode_analisar

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


def termos_de_uso(request):
    return render(request, 'acessos/termos.html')


def politica_privacidade(request):
    return render(request, 'acessos/privacidade.html')


@login_required
def fila_aprovacao(request):
    if not pode_aprovar_acessos(request.user):
        raise PermissionDenied

    pendentes = (
        solicitacoes_que_pode_analisar(request.user)
        .filter(status=SolicitacaoAcesso.Status.PENDENTE)
        .select_related('usuario', 'aluno', 'aluno__turma')
    )
    return render(request, 'acessos/fila.html', {'pendentes': pendentes})


def _pedido_pendente(request, pk):
    # Busca só entre os pedidos que ESTE usuário pode analisar.
    # Pedido de outra turma responde 404: nem revela que existe.
    return get_object_or_404(
        solicitacoes_que_pode_analisar(request.user),
        pk=pk,
        status=SolicitacaoAcesso.Status.PENDENTE,
    )


@login_required
@require_POST
def aprovar_solicitacao(request, pk):
    solicitacao = _pedido_pendente(request, pk)
    usuario = solicitacao.usuario

    # As quatro partes da aprovação: todas ou nenhuma.
    with transaction.atomic():
        usuario.is_active = True
        usuario.save(update_fields=['is_active'])

        perfil, _ = Perfil.objects.get_or_create(
            usuario=usuario,
            defaults={'tipo': Perfil.Tipo.RESPONSAVEL},
        )
        perfil.alunos.add(solicitacao.aluno)

        solicitacao.status = SolicitacaoAcesso.Status.APROVADA
        solicitacao.analisado_por = request.user
        solicitacao.analisado_em = timezone.now()
        solicitacao.save()

    messages.success(request, f'Acesso de {usuario.get_full_name()} aprovado.')
    return redirect('fila_aprovacao')


@login_required
@require_POST
def recusar_solicitacao(request, pk):
    solicitacao = _pedido_pendente(request, pk)
    justificativa = request.POST.get('justificativa', '').strip()

    if not justificativa:
        messages.error(request, 'Para recusar, escreva a justificativa.')
        return redirect('fila_aprovacao')

    solicitacao.status = SolicitacaoAcesso.Status.RECUSADA
    solicitacao.analisado_por = request.user
    solicitacao.analisado_em = timezone.now()
    solicitacao.justificativa = justificativa
    solicitacao.save()

    nome = solicitacao.usuario.get_full_name()
    messages.success(request, f'Pedido de {nome} recusado.')
    return redirect('fila_aprovacao')