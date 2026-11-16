"""Backend de e-mail que usa a API do Brevo em vez de SMTP.

Por que isto existe: o Django sabe sozinho mandar a mensagem de recuperação
de senha, com o token de uso único, mas ele a entrega pelo canal configurado
em EMAIL_BACKEND, que por padrão é SMTP. O projeto já integra um serviço de
e-mail transacional por API HTTP, e manter dois caminhos de envio seria ter
a mesma informação em dois lugares: duas credenciais, dois tratamentos de
erro, duas coisas para configurar no servidor.

Esta classe encaixa a API que já existe no lugar do SMTP. Assim, qualquer
mensagem que o Django resolva enviar — inclusive a de recuperação de senha —
sai pelo mesmo caminho dos avisos de aprovação e de resposta de solicitação.
"""

from django.core.mail.backends.base import BaseEmailBackend

from .notificacoes import enviar_email


class BrevoEmailBackend(BaseEmailBackend):

    def send_messages(self, mensagens):
        """Devolve quantas mensagens saíram.

        O contrato do Django é este: devolver o número de mensagens
        enviadas. Quando fail_silently está ligado, uma falha não derruba a
        operação que pediu o envio — e é esse o comportamento que o projeto
        adota desde o RF04, para que a indisponibilidade de um serviço
        externo não desfaça o que já foi gravado no banco.
        """
        if not mensagens:
            return 0

        enviadas = 0
        for mensagem in mensagens:
            corpo = mensagem.body
            for destinatario in mensagem.to:
                deu_certo, detalhe = enviar_email(
                    destinatario, destinatario, mensagem.subject, corpo,
                )
                if deu_certo:
                    enviadas += 1
                elif not self.fail_silently:
                    raise RuntimeError(
                        f'falha ao enviar e-mail: {detalhe}'
                    )
        return enviadas
