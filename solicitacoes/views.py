# ----------------------------------------------------------------------
# MAPA DO CODIGO
#   O QUE FAZ........: Telas das solicitacoes: listar, abrir, responder
#                      e encerrar.
#   REQUISITOS.......: RF10
#   PROCURE POR......: lista, abrir, responder, encerrar, require_POST,
#                      aviso por e-mail
# ----------------------------------------------------------------------

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from acessos.notificacoes import enviar_email
from auditoria.models import Evento
from auditoria.services import registrar

from .forms import RespostaForm, SolicitacaoForm
from .models import Solicitacao
from .permissions import (
    pode_abrir_solicitacao,
    pode_encerrar,
    pode_responder,
    pode_responder_solicitacoes,
    solicitacoes_visiveis,
)


@login_required
def lista_solicitacoes(request):
    solicitacoes = list(solicitacoes_visiveis(request.user))

    # O template nao chama funcao com argumento, entao a resposta de
    # "posso agir NESTA solicitacao" e calculada aqui e pendurada em cada
    # objeto. A regra continua morando em permissions.py.
    for solicitacao in solicitacoes:
        solicitacao.pode_responder = pode_responder(request.user, solicitacao)
        solicitacao.pode_encerrar = pode_encerrar(request.user, solicitacao)

    return render(request, 'solicitacoes/lista_solicitacoes.html', {
        'solicitacoes': solicitacoes,
        'pode_abrir': pode_abrir_solicitacao(request.user),
        'eh_equipe': pode_responder_solicitacoes(request.user),
    })


@login_required
def abrir_solicitacao(request):
    if not pode_abrir_solicitacao(request.user):
        raise PermissionDenied

    if request.method == 'POST':
        form = SolicitacaoForm(request.POST)
    else:
        form = SolicitacaoForm()

    # So os filhos de quem esta na tela. Sem isto, bastaria forjar o id de
    # outra crianca no envio para abrir solicitacao em nome dela.
    form.fields['aluno'].queryset = request.user.perfil.alunos.all()

    if request.method == 'POST' and form.is_valid():
        solicitacao = form.save(commit=False)
        solicitacao.autor = request.user
        solicitacao.save()
        registrar(
            Evento.Acao.SOLICITACAO_ABERTA,
            usuario=request.user,
            detalhe=f'{solicitacao.aluno.turma} / {solicitacao.assunto}',
        )
        messages.success(
            request,
            'Solicitação enviada. A escola responde por aqui e avisa você '
            'por e-mail.',
        )
        return redirect('lista_solicitacoes')

    return render(request, 'solicitacoes/abrir_solicitacao.html', {
        'form': form,
    })


@login_required
def responder_solicitacao(request, pk):
    solicitacao = get_object_or_404(Solicitacao, pk=pk)

    if not pode_responder(request.user, solicitacao):
        raise PermissionDenied

    if request.method == 'POST':
        form = RespostaForm(request.POST)
    else:
        form = RespostaForm()

    if request.method == 'POST' and form.is_valid():
        solicitacao.responder(request.user, form.cleaned_data['texto'])
        registrar(
            Evento.Acao.SOLICITACAO_RESPONDIDA,
            usuario=request.user,
            detalhe=f'{solicitacao.aluno.turma} / {solicitacao.assunto}',
        )
        _avisar_familia(request, solicitacao)
        return redirect('lista_solicitacoes')

    return render(request, 'solicitacoes/responder_solicitacao.html', {
        'form': form,
        'solicitacao': solicitacao,
    })


@login_required
@require_POST
def encerrar_solicitacao(request, pk):
    # require_POST: encerrar muda o estado, entao nao acontece por um
    # endereco digitado na barra do navegador. Um GET aqui responde 405.
    solicitacao = get_object_or_404(Solicitacao, pk=pk)

    if not pode_encerrar(request.user, solicitacao):
        raise PermissionDenied

    solicitacao.encerrar()
    registrar(
        Evento.Acao.SOLICITACAO_ENCERRADA,
        usuario=request.user,
        detalhe=f'{solicitacao.aluno.turma} / {solicitacao.assunto}',
    )
    messages.success(request, 'Solicitação encerrada.')
    return redirect('lista_solicitacoes')


def _avisar_familia(request, solicitacao):
    """Mesmo tratamento de excecao do RF04: a falha no envio NAO desfaz a
    resposta, que ja esta gravada, e fica registrada no log."""
    familia = solicitacao.autor
    assunto = 'A escola respondeu sua solicitação'
    texto = (
        f'Olá, {familia.get_full_name() or familia.username}.\n\n'
        f'A escola respondeu a solicitação "{solicitacao.assunto}".\n\n'
        'Acesse o Elo Escolar para ler a resposta.\n'
    )
    deu_certo, detalhe = enviar_email(
        familia.email, familia.get_full_name(), assunto, texto,
    )
    registrar(
        Evento.Acao.EMAIL,
        usuario=request.user,
        detalhe=f'{familia.email} / {"enviado" if deu_certo else detalhe}',
    )
    if not deu_certo:
        messages.error(
            request,
            'A resposta foi salva, mas o aviso por e-mail não saiu.',
        )
