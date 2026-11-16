"""Telas de recuperação de senha (RF13).

O mecanismo é o do próprio Django: ele gera uma ligação de uso único,
assinada e com prazo de validade, e só aceita a redefinição quem abrir essa
ligação. Nada de senha trafegando por e-mail, e nenhum token guardado no
banco — a validade é verificada pela assinatura.

O que estas classes acrescentam ao que o framework já faz é o registro no
log de auditoria, de modo que o pedido e a troca efetiva fiquem rastreáveis,
como toda ação relevante do sistema.
"""

from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy

from auditoria.models import Evento
from auditoria.services import registrar


# Os nomes dos arquivos sao proprios, e nao os padroes do Django, por um
# motivo concreto: o aplicativo de administracao ja traz templates chamados
# registration/password_reset_*.html, e ele vem antes deste na lista de
# aplicativos. Com os nomes padrao, os dele venceriam e as telas sairiam com
# a cara do admin.
class PedirRedefinicaoView(auth_views.PasswordResetView):
    template_name = 'acessos/senha_pedir.html'
    email_template_name = 'acessos/senha_email.txt'
    subject_template_name = 'acessos/senha_assunto.txt'
    success_url = reverse_lazy('password_reset_done')

    def form_valid(self, form):
        # O endereço informado é registrado em usuario_informado, e não em
        # usuario: quem pede a redefinição ainda não está autenticado, e o
        # endereço pode nem existir no sistema. Guardar a tentativa é o que
        # permite perceber, depois, alguém varrendo endereços.
        registrar(
            Evento.Acao.SENHA_REDEFINICAO_PEDIDA,
            usuario_informado=form.cleaned_data.get('email', ''),
        )
        return super().form_valid(form)


class RedefinicaoEnviadaView(auth_views.PasswordResetDoneView):
    template_name = 'acessos/senha_enviado.html'


class ConfirmarRedefinicaoView(auth_views.PasswordResetConfirmView):
    template_name = 'acessos/senha_nova.html'
    success_url = reverse_lazy('password_reset_complete')

    def form_valid(self, resposta):
        # Aqui a identidade já está provada pela ligação assinada, então o
        # evento aponta para a conta.
        registrar(
            Evento.Acao.SENHA_REDEFINIDA,
            usuario=self.user,
        )
        return super().form_valid(resposta)


class RedefinicaoConcluidaView(auth_views.PasswordResetCompleteView):
    template_name = 'acessos/senha_pronta.html'
