from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from auditoria.models import Evento
from auditoria.services import registrar
from relatorios.models import Perfil

from .forms import CadastroResponsavelForm, CodigoForm
from .models import (
    MAXIMO_DE_TENTATIVAS,
    VALIDADE_DO_CODIGO_MINUTOS,
    VERSAO_TERMOS,
    AceiteTermos,
    ConfirmacaoEmail,
    SolicitacaoAcesso,
)
from .notificacoes import enviar_email
from .permissions import pode_aprovar_acessos, solicitacoes_que_pode_analisar

User = get_user_model()


def cadastro_responsavel(request):
    if request.method == 'POST':
        form = CadastroResponsavelForm(request.POST)
        if form.is_valid() and form.usuario_pendente is not None:
            # Cadastro que parou antes de confirmar o e-mail: retoma em vez
            # de recusar. A senha e os dados gravados no primeiro cadastro
            # continuam valendo - esta tela não altera nada da conta.
            usuario = form.usuario_pendente
            _mandar_codigo(request, usuario)
            request.session['confirmacao_usuario_id'] = usuario.id
            messages.info(
                request,
                'Este cadastro já tinha sido iniciado e ainda não foi '
                'confirmado. Enviamos um código novo para o seu e-mail.',
            )
            return redirect('confirmar_email')

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
                # Mesmo aceite, agora na tabela que vale para todo usuario.
                AceiteTermos.objects.create(
                    usuario=usuario,
                    versao=VERSAO_TERMOS,
                )
            # RF14: o e-mail informado ainda nao foi provado. Antes de
            # o pedido chegar a escola, a pessoa precisa confirmar que o
            # endereco e dela.
            _mandar_codigo(request, usuario)
            request.session['confirmacao_usuario_id'] = usuario.id
            return redirect('confirmar_email')
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
def aceitar_termos(request):
    # Tela de bloqueio: quem nao aceitou a versao vigente para aqui.
    destino = request.POST.get('next') or request.GET.get('next') or ''
    # So aceita voltar para dentro do proprio site.
    if not url_has_allowed_host_and_scheme(destino, {request.get_host()}):
        destino = ''
    if request.method == 'POST':
        if request.POST.get('aceite'):
            AceiteTermos.objects.get_or_create(
                usuario=request.user,
                versao=VERSAO_TERMOS,
            )
            registrar(
                Evento.Acao.TERMOS_ACEITOS,
                usuario=request.user,
                detalhe=f'versao {VERSAO_TERMOS}',
            )
            return redirect(destino or 'lista_relatorios')
        messages.error(request, 'É preciso marcar a caixa para continuar.')
    return render(request, 'acessos/aceitar_termos.html', {
        'destino': destino,
        'versao': VERSAO_TERMOS,
    })


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


def _mandar_codigo(request, usuario):
    """Gera um codigo novo e manda por e-mail. Registra o envio no log."""
    _, codigo = ConfirmacaoEmail.gerar(usuario)
    assunto = 'Elo Escolar - confirme seu e-mail'
    texto = (
        f'Olá, {usuario.get_full_name() or usuario.username}.\n\n'
        f'Seu código de confirmação é: {codigo}\n\n'
        f'Ele vale por {VALIDADE_DO_CODIGO_MINUTOS} minutos e só pode ser '
        'usado uma vez.\n\n'
        'Se não foi você quem se cadastrou no Elo Escolar, ignore esta '
        'mensagem.\n'
    )
    deu_certo, detalhe = enviar_email(
        usuario.email, usuario.get_full_name(), assunto, texto,
    )
    registrar(
        Evento.Acao.EMAIL,
        usuario_informado=usuario.email,
        detalhe=f'código de confirmação / {"enviado" if deu_certo else detalhe}',
    )
    return deu_certo


def _confirmacao_da_sessao(request):
    """Quem esta confirmando nao esta autenticado: a conta nasce desligada.

    Por isso a identidade vem da sessao, gravada no momento do cadastro, e
    nao de um id na barra de enderecos - que permitiria tentar codigos de
    outras pessoas.
    """
    usuario_id = request.session.get('confirmacao_usuario_id')
    if not usuario_id:
        return None
    return ConfirmacaoEmail.objects.filter(usuario_id=usuario_id).first()


def confirmar_email(request):
    confirmacao = _confirmacao_da_sessao(request)
    if confirmacao is None:
        return redirect('cadastro')

    if confirmacao.confirmado:
        return redirect('cadastro_enviado')

    if request.method == 'POST':
        form = CodigoForm(request.POST)
    else:
        form = CodigoForm()

    if request.method == 'POST' and form.is_valid():
        deu_certo, motivo = confirmacao.conferir(form.cleaned_data['codigo'])
        if deu_certo:
            registrar(
                Evento.Acao.EMAIL_CONFIRMADO,
                usuario_informado=confirmacao.usuario.email,
            )
            del request.session['confirmacao_usuario_id']
            return redirect('cadastro_enviado')

        if motivo == 'expirado':
            messages.error(
                request,
                'Este código expirou. Peça outro para continuar.',
            )
        elif motivo == 'tentativas esgotadas':
            messages.error(
                request,
                'Número de tentativas esgotado. Peça um código novo.',
            )
        else:
            restantes = MAXIMO_DE_TENTATIVAS - confirmacao.tentativas
            messages.error(
                request,
                f'Código incorreto. Você ainda tem {restantes} '
                f'{"tentativa" if restantes == 1 else "tentativas"}.',
            )

    return render(request, 'acessos/confirmar_email.html', {
        'form': form,
        'email': confirmacao.usuario.email,
        'validade': VALIDADE_DO_CODIGO_MINUTOS,
    })


@require_POST
def reenviar_codigo(request):
    confirmacao = _confirmacao_da_sessao(request)
    if confirmacao is None:
        return redirect('cadastro')

    if confirmacao.confirmado:
        return redirect('cadastro_enviado')

    _mandar_codigo(request, confirmacao.usuario)
    messages.success(request, 'Enviamos um código novo para o seu e-mail.')
    return redirect('confirmar_email')
