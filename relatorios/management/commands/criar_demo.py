"""Cria os dados de demonstração do Elo Escolar.

Por que isto é um comando do Django, e não um script solto: o servidor de
produção do plano gratuito não oferece terminal, então a única maneira de
povoar o banco é a partir do processo de publicação. Um comando de
gerenciamento é chamado por `python manage.py criar_demo`, dentro ou fora do
servidor, e não precisa configurar o Django por conta própria.

A senha nunca fica escrita aqui. Ela vem da variável de ambiente DEMO_SENHA;
não havendo variável, uma senha é sorteada e impressa na tela. Assim este
arquivo pode ficar no repositório, que é público, sem carregar segredo algum.

O comando é idempotente: rodar duas vezes não duplica nada.
"""

import os
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from acessos.models import VERSAO_TERMOS, AceiteTermos, ConfirmacaoEmail
from recados.models import Recado
from relatorios.models import Aluno, Perfil, RelatorioDiario, Turma
from solicitacoes.models import Solicitacao

User = get_user_model()

# Domínio reservado para testes: nenhum endereço aqui pertence a uma pessoa
# real, e nada enviado a ele sai para a internet.
DOMINIO = 'example.com'

PESSOAS = [
    ('ana.diretora', 'Ana', 'Ribeiro', Perfil.Tipo.DIRETOR),
    ('joao.pereira', 'João', 'Pereira', Perfil.Tipo.COORDENADOR),
    ('marcia.silva', 'Márcia', 'Silva', Perfil.Tipo.PROFESSOR),
    ('carla.nunes', 'Carla', 'Nunes', Perfil.Tipo.PROFESSOR),
    ('bia.alves', 'Beatriz', 'Alves', Perfil.Tipo.RESPONSAVEL),
    ('rui.campos', 'Rui', 'Campos', Perfil.Tipo.RESPONSAVEL),
]

# Conta tecnica da demonstracao. Ela NAO tem perfil, e isso e
# proposital: nao corresponde a nenhuma pessoa da escola e nao deve
# aparecer como professor, coordenador ou responsavel em tela alguma. Ela
# existe para dar acesso ao painel administrativo do Django, sem o qual
# dois passos do roteiro de verificacao do Apendice A nao sao reproduziveis
# - o que mostra que o relatorio excluido continua no banco, e o que
# remove o aceite dos Termos para ver o bloqueio.
CONTA_TECNICA = ('admin.demo', 'Administração', 'da demonstração')

TURMAS = [
    ('1 ANO A', 'marcia.silva'),
    ('2 ANO B', 'marcia.silva'),
    ('3 ANO C', 'carla.nunes'),
]

ALUNOS = [
    ('Pedro Souza', '2026001', '1 ANO A'),
    ('Lívia Martins', '2026002', '1 ANO A'),
    ('Caio Duarte', '2026003', '2 ANO B'),
    ('Helena Rocha', '2026004', '2 ANO B'),
    ('Theo Barbosa', '2026005', '3 ANO C'),
    ('Alice Moreira', '2026006', '3 ANO C'),
]

# Qual responsável acompanha quais alunos.
VINCULOS = {
    'bia.alves': ['2026001', '2026003'],
    'rui.campos': ['2026005'],
}


class Command(BaseCommand):
    help = 'Cria usuários, turmas, alunos e conteúdo de demonstração.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--senha',
            help='Senha das contas de demonstração. Sem isto, usa a '
                 'variável de ambiente DEMO_SENHA ou sorteia uma.',
        )

    def handle(self, *args, **opcoes):
        senha = (opcoes.get('senha')
                 or os.environ.get('DEMO_SENHA')
                 or f'demo-{secrets.token_urlsafe(9)}')

        pessoas = self._criar_pessoas(senha)
        self._criar_conta_tecnica(senha)
        turmas = self._criar_turmas(pessoas)
        alunos = self._criar_alunos(turmas)
        self._vincular(pessoas, alunos)
        self._criar_conteudo(pessoas, turmas, alunos)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Dados de demonstração prontos.'))
        self.stdout.write('')
        for usuario, nome, sobrenome, tipo in PESSOAS:
            rotulo = Perfil.Tipo(tipo).label
            self.stdout.write(f'  {usuario}@{DOMINIO}  —  {rotulo}')
        usuario_tecnico = CONTA_TECNICA[0]
        self.stdout.write('')
        self.stdout.write(
            f'  {usuario_tecnico}@{DOMINIO}  —  painel administrativo '
            f'(/admin/), sem perfil no sistema')
        self.stdout.write('')
        self.stdout.write(f'  senha de todas as contas: {senha}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            'Troque essa senha antes de qualquer uso que não seja '
            'demonstração.'))

    # ------------------------------------------------------------------
    def _conta_por_email(self, email):
        """Devolve (conta, nova), com o e-mail tambem no campo de usuario.

        No Elo Escolar o login E o e-mail: e assim que o cadastro publico
        grava a conta do responsavel, e e o que a tela de entrada promete.
        Este comando gravava o nome curto no campo de usuario e o e-mail
        so no campo de e-mail, criando duas convencoes dentro do mesmo
        sistema - e as contas de demonstracao nao entravam pelo endereco
        que a propria tela mostra.

        A busca e feita pelo e-mail, e nao pelo nome de usuario, para que
        uma conta gravada na convencao antiga seja corrigida em vez de
        duplicada na proxima execucao.
        """
        conta = User.objects.filter(email=email).first()
        if conta is None:
            return User(username=email, email=email), True
        conta.username = email
        return conta, False

    def _criar_pessoas(self, senha):
        pessoas = {}
        for usuario, nome, sobrenome, tipo in PESSOAS:
            email = f'{usuario}@{DOMINIO}'
            conta, nova = self._conta_por_email(email)
            conta.first_name = nome
            conta.last_name = sobrenome
            conta.is_staff = tipo in (Perfil.Tipo.DIRETOR,
                                      Perfil.Tipo.COORDENADOR)
            # A senha é sempre reescrita: é o que permite rodar o comando de
            # novo para recuperar o acesso sem apagar os dados.
            conta.set_password(senha)
            conta.is_active = True
            conta.save()

            Perfil.objects.get_or_create(usuario=conta,
                                         defaults={'tipo': tipo})
            AceiteTermos.objects.get_or_create(usuario=conta,
                                               versao=VERSAO_TERMOS)
            # Contas de demonstração já nascem com o e-mail confirmado;
            # do contrário o RF14 as trataria como cadastro inacabado.
            confirmacao, _ = ConfirmacaoEmail.gerar(conta)
            confirmacao.confirmado_em = timezone.now()
            confirmacao.save(update_fields=['confirmado_em'])

            pessoas[usuario] = conta
            if nova:
                self.stdout.write(f'  conta criada: {usuario}')
        return pessoas

    def _criar_conta_tecnica(self, senha):
        """Conta com acesso ao painel administrativo do Django.

        Recebe o aceite dos Termos como as demais: o middleware do projeto
        cobre TODA requisicao, inclusive as do painel administrativo, entao
        sem o aceite esta conta seria desviada para a tela de aceite ao
        tentar abrir /admin/.

        Nao recebe Perfil: perfil e o que diz de qual pessoa da escola se
        trata, e esta conta nao e de ninguem - e ferramenta.
        """
        usuario, nome, sobrenome = CONTA_TECNICA
        conta, nova = self._conta_por_email(f'{usuario}@{DOMINIO}')
        conta.first_name = nome
        conta.last_name = sobrenome
        conta.is_staff = True
        conta.is_superuser = True
        conta.is_active = True
        conta.set_password(senha)
        conta.save()

        AceiteTermos.objects.get_or_create(usuario=conta,
                                           versao=VERSAO_TERMOS)
        if nova:
            self.stdout.write(f'  conta tecnica criada: {usuario}')
        return conta

    def _criar_turmas(self, pessoas):
        turmas = {}
        for nome, professor in TURMAS:
            turma, _ = Turma.objects.get_or_create(
                nome=nome, ano_letivo=2026,
                defaults={'professor': pessoas[professor]},
            )
            turmas[nome] = turma
        return turmas

    def _criar_alunos(self, turmas):
        alunos = {}
        for nome, rgm, turma in ALUNOS:
            aluno, _ = Aluno.objects.get_or_create(
                rgm=rgm,
                defaults={'nome_completo': nome, 'turma': turmas[turma]},
            )
            alunos[rgm] = aluno
        return alunos

    def _vincular(self, pessoas, alunos):
        for usuario, rgms in VINCULOS.items():
            perfil = pessoas[usuario].perfil
            perfil.alunos.set([alunos[rgm] for rgm in rgms])

    def _criar_conteudo(self, pessoas, turmas, alunos):
        hoje = timezone.localdate()

        conteudos = [
            ('1 ANO A', 'marcia.silva', 1,
             'Roda de leitura e contagem até cem. A turma trabalhou em duplas.',
             'Trazer um objeto de casa que comece com a letra P.'),
            ('2 ANO B', 'marcia.silva', 1,
             'Revisão de adição com reagrupamento e leitura compartilhada.',
             'Terminar a página 14 do livro de matemática.'),
            ('3 ANO C', 'carla.nunes', 2,
             'Experiência sobre o ciclo da água, com registro no caderno.',
             ''),
            ('1 ANO A', 'marcia.silva', 3,
             'Atividade de escrita espontânea e jogo de rimas.', ''),
        ]
        for turma, autor, dias_atras, conteudo, tarefa in conteudos:
            RelatorioDiario.objects.get_or_create(
                turma=turmas[turma],
                data_aula=hoje - timedelta(days=dias_atras),
                defaults={
                    'conteudo': conteudo,
                    'tarefa_descricao': tarefa,
                    'autor': pessoas[autor],
                },
            )

        Recado.objects.get_or_create(
            titulo='Reunião de pais e mestres',
            defaults={
                'turma': None,
                'mensagem': 'A reunião acontece no dia 5, às 19h, no pátio '
                            'coberto. A presença de ao menos um responsável '
                            'é importante.',
                'exibir_ate': hoje + timedelta(days=20),
                'autor': pessoas['joao.pereira'],
            },
        )
        Recado.objects.get_or_create(
            titulo='Passeio ao parque municipal',
            defaults={
                'turma': turmas['1 ANO A'],
                'mensagem': 'A saída é às 8h e o retorno às 12h. Enviar '
                            'garrafa de água e boné.',
                'exibir_ate': hoje + timedelta(days=10),
                'autor': pessoas['marcia.silva'],
            },
        )

        pedido, criado = Solicitacao.objects.get_or_create(
            aluno=alunos['2026001'],
            autor=pessoas['bia.alves'],
            assunto='Falta do dia 12',
            defaults={
                'tipo': Solicitacao.Tipo.JUSTIFICATIVA,
                'descricao': 'O Pedro faltou por consulta médica. Posso '
                             'levar o atestado amanhã?',
            },
        )
        if criado:
            pedido.responder(
                pessoas['marcia.silva'],
                'Pode trazer amanhã, sem problema. Já registrei a '
                'justificativa aqui.',
            )

        Solicitacao.objects.get_or_create(
            aluno=alunos['2026005'],
            autor=pessoas['rui.campos'],
            assunto='Conversar sobre a leitura',
            defaults={
                'tipo': Solicitacao.Tipo.CONTATO,
                'descricao': 'Gostaria de conversar sobre o desempenho do '
                             'Theo em leitura. Qual o melhor horário?',
            },
        )
