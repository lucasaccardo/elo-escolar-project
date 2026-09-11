# \# Elo Escolar

# 

# Sistema web para centralizar e registrar a comunicação entre a equipe pedagógica e os responsáveis nos anos iniciais do Ensino Fundamental.

# 

# \## Sobre o projeto

# 

# A comunicação entre escola e família ocorre, em grande parte, por canais informais e fragmentados — grupos de mensagens, recados manuscritos e ligações telefônicas. Esse cenário compromete o registro e o acompanhamento das informações.

# 

# O Elo Escolar substitui esses meios por um canal único, digital e rastreável, no qual a equipe pedagógica publica os registros da turma e os responsáveis os consultam a qualquer momento.

# 

# Projeto Final de Curso — Engenharia de Software — Universidade de Mogi das Cruzes (UMC), 2026.

# 

# \## Funcionalidade implementada nesta entrega

# 

# Primeira regra de negócio completa: \*\*relatório diário de aula\*\*.

# 

# \- Cadastro de turmas (nome e ano letivo), pelo painel administrativo

# \- Publicação do relatório diário pela equipe pedagógica, com data da aula, conteúdo trabalhado, tarefa de casa (opcional), data de entrega da tarefa (opcional) e observações (opcional)

# \- Registro automático do autor e da data/hora de publicação

# \- Listagem dos relatórios em ordem cronológica decrescente, exibindo apenas os campos preenchidos

# \- Validação dos dados no envio do formulário

# 

# As demais funcionalidades previstas (autenticação por perfil, solicitações/tickets, recados, dashboard e notificações por e-mail) serão implementadas nas etapas seguintes.

# 

# \## Tecnologias

# 

# | Tecnologia | Versão | Uso |

# |---|---|---|

# | Python | 3.12.10 | linguagem |

# | Django | 6.1.1 | framework web (padrão MVT) |

# | SQLite | 3 | banco de dados em desenvolvimento |

# | Bootstrap | 5.3.0 | estilos e responsividade |

# | python-decouple | 3.8 | leitura de variáveis de ambiente |

# | Git | 2.55.0 | versionamento |

# 

# Em produção está previsto o uso de PostgreSQL.

# 

# \## Como executar localmente

# 

# Os comandos abaixo assumem Windows. Em Linux ou macOS, o único passo diferente é a ativação do ambiente virtual: `source venv/bin/activate`.

# 

# \*\*1. Clonar o repositório\*\*

# 

# ```

# git clone https://github.com/lucasaccardo/elo-escolar-project.git

# ```

# 

# \*\*2. Entrar na pasta do projeto\*\*

# 

# ```

# cd elo-escolar-project

# ```

# 

# \*\*3. Criar o ambiente virtual\*\*

# 

# ```

# python -m venv venv

# ```

# 

# \*\*4. Ativar o ambiente virtual\*\*

# 

# ```

# venv\\Scripts\\activate

# ```

# 

# A partir daqui, a linha do terminal deve começar com `(venv)`.

# 

# \*\*5. Instalar as dependências\*\*

# 

# ```

# pip install -r requirements.txt

# ```

# 

# \*\*6. Criar o arquivo de variáveis de ambiente\*\*

# 

# ```

# copy .env.example .env

# ```

# 

# \*\*7. Gerar uma SECRET\_KEY\*\*

# 

# ```

# python -c "from django.core.management.utils import get\_random\_secret\_key; print(get\_random\_secret\_key())"

# ```

# 

# Copie a chave gerada e cole no arquivo `.env`, após o sinal de igual, sem aspas e sem espaços:

# 

# ```

# SECRET\_KEY=chave-gerada-no-passo-anterior

# DEBUG=True

# ```

# 

# \*\*8. Criar as tabelas no banco de dados\*\*

# 

# ```

# python manage.py migrate

# ```

# 

# \*\*9. Criar o usuário administrador\*\*

# 

# ```

# python manage.py createsuperuser

# ```

# 

# \*\*10. Executar o servidor\*\*

# 

# ```

# python manage.py runserver

# ```

# 

# O sistema fica disponível em `http://127.0.0.1:8000` e o painel administrativo em `http://127.0.0.1:8000/admin`.

# 

# Antes de publicar um relatório, cadastre ao menos uma turma pelo painel administrativo — o relatório depende de uma turma existente.

# 

# \## Estrutura de pastas

# 

# ```

# elo-escolar/

# ├── config/                     configurações do projeto

# │   ├── settings.py             banco, apps instalados, idioma, fuso, arquivos estáticos

# │   └── urls.py                 distribuição das rotas

# ├── relatorios/                 aplicação do relatório diário

# │   ├── migrations/             instruções de criação das tabelas

# │   ├── templates/relatorios/   base.html, lista\_relatorios.html, cadastrar\_relatorio.html

# │   ├── admin.py                registro dos modelos no painel administrativo

# │   ├── forms.py                formulário do relatório diário

# │   ├── models.py               modelos Turma e RelatorioDiario

# │   ├── urls.py                 rotas da aplicação

# │   └── views.py                listagem e cadastro

# ├── static/img/                 logotipo e imagens de fundo

# ├── .env.example                modelo das variáveis de ambiente

# ├── .gitignore                  arquivos fora do versionamento

# ├── manage.py                   utilitário de linha de comando do Django

# └── requirements.txt            dependências com versões fixas

# ```

# 

# \## Segurança e dados

# 

# A `SECRET\_KEY` e as demais credenciais não são versionadas: ficam no arquivo `.env`, bloqueado pelo `.gitignore`. O arquivo `.env.example` documenta quais variáveis são necessárias, sem expor seus valores.

# 

# O banco de dados local (`db.sqlite3`) também está fora do versionamento, por conter dados pessoais.

# 

# \## Status

# 

# Em desenvolvimento.

# 

# Branch `main` — versão de trabalho.

# Branch `entrega1409` — versão submetida à avaliação de 14/09/2026.

# 

# \## Autor

# 

# Lucas Mateus Sureira — Engenharia de Software, UMC

# Orientador: Prof. Lucas dos Santos da Silva

