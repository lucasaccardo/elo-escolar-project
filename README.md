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