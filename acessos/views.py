from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from auditoria.models import Evento
from auditoria.services import registrar
from relatorios.models import Perfil

from .forms import CadastroResponsavelForm
from .models import SolicitacaoAcesso
from .notificacoes import enviar_email
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


# A mesma mensagem para todos os casos: pedido que não existe, de outra
# turma ou já analisado. Assim a tela não revela qual foi o motivo.
AVISO_INDISPONIVEL = (
    'Não foi possível concluir: este pedido já foi analisado '
    'ou não está disponível para você.'
)


def _pedido_pendente(request, pk):
    # Busca só entre os pedidos que ESTE usuário pode analisar.
    # Se não achar, devolve None em vez de mostrar a página de erro.
    return (
        solicitacoes_que_pode_analisar(request.user)
        .filter(pk=pk, status=SolicitacaoAcesso.Status.PENDENTE)
        .first()
    )


def _avisar_por_email(request, usuario, assunto, texto):
    # Chama a API e registra no log se o aviso saiu ou não.
    deu_certo, detalhe = enviar_email(
        usuario.email, usuario.get_full_name(), assunto, texto,
    )
    registrar(
        Evento.Acao.EMAIL,
        usuario=request.user,
        detalhe=f'{usuario.email} / {"enviado" if deu_certo else detalhe}',
    )
    if not deu_certo:
        messages.error(
            request,
            'A decisão foi salva, mas o aviso por e-mail não saiu.',
        )


@login_required
@require_POST
def aprovar_solicitacao(request, pk):
    solicitacao = _pedido_pendente(request, pk)
    if solicitacao is None:
        messages.error(request, AVISO_INDISPONIVEL)
        return redirect('fila_aprovacao')

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

        registrar(
            Evento.Acao.ACESSO_APROVADO,
            usuario=request.user,
            detalhe=f'{usuario.username} / aluno {solicitacao.aluno.rgm}',
        )

    _avisar_por_email(
        request,
        usuario,
        'Seu acesso ao Elo Escolar foi liberado',
        f'Olá, {usuario.first_name}. A escola confirmou o seu vínculo e o '
        f'seu acesso foi liberado. Entre com o seu e-mail e a senha que '
        f'você criou no cadastro.',
    )

    messages.success(request, f'Acesso de {usuario.get_full_name()} aprovado.')
    return redirect('fila_aprovacao')


@login_required
@require_POST
def recusar_solicitacao(request, pk):
    solicitacao = _pedido_pendente(request, pk)
    if solicitacao is None:
        messages.error(request, AVISO_INDISPONIVEL)
        return redirect('fila_aprovacao')

    justificativa = request.POST.get('justificativa', '').strip()

    if not justificativa:
        messages.error(request, 'Para recusar, escreva a justificativa.')
        return redirect('fila_aprovacao')

    solicitacao.status = SolicitacaoAcesso.Status.RECUSADA
    solicitacao.analisado_por = request.user
    solicitacao.analisado_em = timezone.now()
    solicitacao.justificativa = justificativa
    solicitacao.save()

    registrar(
        Evento.Acao.ACESSO_RECUSADO,
        usuario=request.user,
        detalhe=f'{solicitacao.usuario.username} / {justificativa}',
    )

    _avisar_por_email(
        request,
        solicitacao.usuario,
        'Sobre o seu pedido de acesso ao Elo Escolar',
        f'Olá, {solicitacao.usuario.first_name}. O seu pedido de acesso não '
        f'pôde ser aprovado. Motivo informado pela escola: {justificativa}. '
        f'Em caso de dúvida, procure a secretaria.',
    )

    nome = solicitacao.usuario.get_full_name()
    messages.success(request, f'Pedido de {nome} recusado.')
    return redirect('fila_aprovacao')