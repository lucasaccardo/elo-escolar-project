# Elo Escolar

Sistema web para centralizar e registrar a comunicação entre a equipe pedagógica e os responsáveis nos anos iniciais do Ensino Fundamental.

## Sobre o projeto

A comunicação entre escola e família ocorre, em grande parte, por canais informais e fragmentados — grupos de mensagens, recados manuscritos e ligações telefônicas. Esse cenário compromete o registro e o acompanhamento das informações.

O Elo Escolar substitui esses meios por um canal único, digital e rastreável, no qual a equipe pedagógica publica os registros da turma e os responsáveis os consultam a qualquer momento.

Projeto Final de Curso — Engenharia de Software — Universidade de Mogi das Cruzes (UMC), 2026.

## O que está implementado (entrega de 28/09/2026)

**1. Login, controle de acesso e criptografia**

- Autenticação pelo `django.contrib.auth`, em `/contas/login/`, com formulário próprio (`acessos/forms.py`, classe `LoginForm`).
- Senhas gravadas como **hash PBKDF2-SHA256 com salt e 1.500.000 iterações** — o sistema nunca guarda a senha.
- Autorização por perfil concentrada em `relatorios/permissions.py` e `acessos/permissions.py`: as views perguntam, os arquivos de permissão decidem. A regra é **negar por padrão** (lista de quem pode).
- Perfis: diretor, coordenador, professor e responsável. O professor vê e publica apenas nas turmas dele; coordenação e direção veem todas; o responsável vê apenas as turmas dos filhos.
- A proteção está na consulta ao banco e na view (`PermissionDenied` → 403), não apenas na tela.
- Conta desligada não entra: o sistema usa o `is_active` do Django. Com a senha correta, a tela informa o motivo (aguardando aprovação, pedido recusado ou acesso desativado); com a senha errada, a mensagem é sempre genérica, para não permitir descobrir contas.

**2. Cadastro e aprovação de acesso (app `acessos`)**

- Cadastro público apenas para responsáveis, em `/acessos/cadastro/`, com vínculo informado pelo RGM do aluno. A tela não exibe o nome da criança.
- A conta nasce desativada. A liberação é feita na fila de aprovação (`/acessos/pedidos/`) por professor (das turmas dele), coordenação ou direção.
- Aprovar executa quatro operações numa única transação: ativa a conta, cria o perfil de responsável, vincula o aluno e registra quem aprovou e quando. Recusar exige justificativa.

**3. Logs de auditoria (app `auditoria`)**

- Model `Evento` registra **o quê, quem e quando**: entrada no sistema, erro de login, aprovação e recusa de acesso, publicação de relatório e envio de e-mail.
- Login e erro de login são capturados pelos sinais `user_logged_in` e `user_login_failed`; as demais ações chamam `auditoria/services.py` → `registrar()`.
- Consulta em `/admin/auditoria/evento/`, com filtro por ação e busca por usuário. O registro é **somente leitura**: não é possível adicionar, alterar ou excluir pelo painel.
- O log não guarda senha, token nem endereço de IP.

**4. LGPD**

- **Termos de Uso:** `/acessos/termos/` · **Política de Privacidade:** `/acessos/privacidade/`
- Escritos para este sistema: descrevem os dados coletados (responsável, aluno, equipe, registros de acesso), a finalidade, quem vê o quê, o prazo de guarda, os direitos do titular (art. 18) e o tratamento de dados de crianças.
- Ficam acessíveis **em todas as telas**, pelo rodapé (`relatorios/templates/relatorios/base.html`), e no aceite do cadastro, que grava a data e a hora do aceite (`SolicitacaoAcesso.aceite_termos_em`).
- Base legal adotada: execução de políticas públicas de educação (Lei nº 13.709/2018, art. 7º, III, e art. 23).
- Minimização: o sistema não coleta CPF do aluno nem endereço, e o relatório é sempre da turma, nunca de um aluno individualmente.

**5. Integração com API externa**

Ver a seção "Integração com API externa — documentação técnica", abaixo.

## Integração com API externa — documentação técnica

**Serviço utilizado:** Brevo — API de e-mail transacional (plano gratuito).

**Por que esta API.** A conta do responsável nasce desativada e só é liberada após a análise da escola. Enquanto isso, ele não consegue entrar no sistema, e portanto não existe canal interno para avisá-lo do resultado. O único canal disponível é o e-mail informado no cadastro — que é também o nome de usuário dele. A mesma integração atende ao aviso de aprovação, ao aviso de recusa com a justificativa e, nas próximas etapas, à recuperação de senha e à confirmação do endereço de e-mail.

A API de CEP (ViaCEP), citada na ficha de caracterização, foi descartada: exigiria coletar endereço, dado que o sistema não utiliza para nenhuma finalidade, o que contraria o princípio da minimização (art. 6º, III, da LGPD).

**Onde está no código:** `acessos/notificacoes.py`, função `enviar_email()`. As chamadas ocorrem em `acessos/views.py`, nas views `aprovar_solicitacao` e `recusar_solicitacao`, por meio da função auxiliar `_avisar_por_email()`.

**Especificação da chamada**

| Item | Valor |
|---|---|
| Endereço | `https://api.brevo.com/v3/smtp/email` |
| Método | POST |
| Autenticação | cabeçalho `api-key`, lido de `BREVO_API_KEY` (arquivo `.env`, fora do versionamento) |
| Formato | JSON (`content-type: application/json`) |
| Tempo limite | 10 segundos |
| Biblioteca | `urllib.request`, da biblioteca padrão do Python — a integração não acrescenta dependências |

**Corpo enviado**

```json
{
  "sender":  {"name": "Elo Escolar", "email": "<EMAIL_REMETENTE>"},
  "to":      [{"email": "<e-mail do responsável>", "name": "<nome>"}],
  "subject": "Seu acesso ao Elo Escolar foi liberado",
  "textContent": "<mensagem>"
}
```

**Respostas tratadas**

| Situação | Tratamento |
|---|---|
| `201 Created` | envio aceito; grava no log de auditoria `Aviso por e-mail / enviado` |
| Erro HTTP (`HTTPError`, ex.: 401 chave inválida, 400 remetente não validado) | grava o código no log e avisa na tela que o e-mail não saiu |
| Falha de rede (`URLError`, ex.: sem internet) | mesmo tratamento, registrando o motivo |
| Chave ou remetente ausentes no `.env` | a chamada nem é feita; o log registra `servico de e-mail nao configurado` |

**Decisão de projeto:** a falha no envio **não desfaz** a aprovação nem a recusa. A decisão da escola já está gravada no banco; o e-mail é um aviso. Por isso o envio acontece fora da transação e o resultado, bem ou mal sucedido, é registrado no log de auditoria.

**Dados enviados ao fornecedor:** apenas nome e e-mail do responsável e o texto do aviso. **Nenhum dado de criança é enviado** — o e-mail não menciona nome nem RGM do aluno.

## Interface

- Folha de estilo própria (`static/css/estilo.css`), sem framework e sem CDN: a aparência do sistema não depende de conexão com a internet. Cores, arredondamentos e sombras ficam em variáveis CSS, reunidas num único bloco `:root`.
- `/` é uma página pública de apresentação. Quem já está autenticado é redirecionado para o diário, em `/relatorios/`.
- O menu lateral é montado por perfil: os itens exibidos são decididos pelos mesmos arquivos `permissions.py` que protegem as views, e não por uma regra própria da tela.
- O filtro de turmas usa abas implementadas como links (`?turma=<id>`): funciona com JavaScript desligado e cada turma tem endereço próprio.
- Acessibilidade: a regra `@media (prefers-reduced-motion: reduce)` desliga transições e animações para quem configurou o sistema operacional pedindo menos movimento.
- O projeto não usa nenhuma biblioteca de JavaScript.

## Tecnologias

| Tecnologia | Versão | Uso |
|---|---|---|
| Python | 3.12.10 | linguagem |
| Django | 6.1.1 | framework web (padrão MVT) |
| SQLite | 3 | banco de dados em desenvolvimento |
| CSS | — | folha de estilo própria (`static/css/estilo.css`), sem framework |
| python-decouple | 3.8 | leitura de variáveis de ambiente |
| Brevo | API v3 | envio de e-mail transacional |
| Git | 2.55.0 | versionamento |

Em produção está previsto o uso de PostgreSQL.

## Estrutura do projeto

```
elo-escolar/
├── config/                       configuração do projeto
│   ├── settings.py               apps instalados, banco, idioma, fuso, senhas
│   └── urls.py                   rotas gerais: admin, contas, acessos, relatórios
├── relatorios/                   domínio do relatório diário de aula
│   ├── models.py                 Turma, Aluno, RelatorioDiario, Perfil
│   ├── permissions.py            quem publica e quais turmas cada perfil enxerga
│   ├── forms.py                  formulário do relatório
│   ├── views.py                  página inicial pública, listagem e publicação
│   ├── urls.py                   rotas do app
│   ├── admin.py                  registro no painel administrativo
│   └── templates/                base.html (casca e menu), inicio.html (vitrine), login e telas do relatório
├── acessos/                      domínio do acesso ao sistema
│   ├── models.py                 SolicitacaoAcesso
│   ├── forms.py                  cadastro do responsável e formulário de login
│   ├── permissions.py            quem pode analisar cada pedido
│   ├── notificacoes.py           integração com a API de e-mail
│   ├── context_processors.py     monta o menu lateral conforme o perfil
│   ├── views.py                  cadastro, fila, aprovação, recusa, termos e política
│   ├── urls.py                   rotas do app
│   └── templates/acessos/        cadastro, fila, termos, política
├── auditoria/                    domínio do log de auditoria
│   ├── models.py                 Evento
│   ├── services.py               função registrar()
│   ├── signals.py                captura de login e de erro de login
│   ├── apps.py                   liga os sinais ao iniciar
│   └── admin.py                  consulta somente leitura
├── static/
│   ├── css/estilo.css            folha de estilo única do sistema
│   └── img/                      logotipo e imagens de fundo
├── .env.example                  modelo das variáveis de ambiente
├── manage.py                     utilitário de linha de comando do Django
└── requirements.txt              dependências com versões fixas
```

Cada app reúne o seu domínio: regras de permissão, modelos, telas e rotas. As views não decidem permissão — elas perguntam aos arquivos `permissions.py`.

## Como executar localmente

Os comandos assumem Windows. Em Linux ou macOS, muda apenas a ativação do ambiente virtual: `source venv/bin/activate`.

```
git clone https://github.com/lucasaccardo/elo-escolar-project.git
cd elo-escolar-project
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Gere a chave secreta e cole no `.env`:

```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

O `.env` deve ficar assim:

```
SECRET_KEY=chave-gerada-acima
DEBUG=True
BREVO_API_KEY=chave-da-api-de-e-mail
EMAIL_REMETENTE=endereco-validado-no-brevo
```

Sem as duas últimas variáveis o sistema funciona normalmente: apenas os avisos por e-mail não são enviados, e o log registra o motivo.

```
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

O sistema fica em `http://127.0.0.1:8000` e o painel administrativo em `http://127.0.0.1:8000/admin`.
A página inicial (`/`) é pública. As demais telas exigem login.

Antes de publicar um relatório, cadastre pelo painel administrativo ao menos uma turma e um aluno.

## Segurança e dados

A `SECRET_KEY`, a chave da API de e-mail e as demais credenciais não são versionadas: ficam no `.env`, bloqueado pelo `.gitignore`. O `.env.example` documenta quais variáveis existem, sem os valores.

O banco local (`db.sqlite3`) também está fora do versionamento. Todos os dados usados em desenvolvimento e nas demonstrações são fictícios.

## Status

Em desenvolvimento.

| Branch | Conteúdo |
|---|---|
| `main` | versão de trabalho |
| `entrega1409` | versão submetida à avaliação de 14/09/2026 |
| `entrega2809` | versão submetida à avaliação de 28/09/2026 |

## Autor

Lucas Mateus Sureira — Engenharia de Software, UMC
Orientador: Prof. Lucas Santos da Silva
