# 🎬 Director Bot
Um bot para Discord desenvolvido em Python focado em buscar, registrar e organizar mídias (filmes e séries) assistidas pelos usuários do servidor, utilizando a API do TMDB. Além do gerenciamento de mídias, o bot conta com uma integração com a Inteligência Artificial do Google Gemini para resumir anotações criativas e discussões do chat.

O bot utiliza banco de dados assíncrono (aiosqlite) para garantir performance máxima sem travar o event loop do Discord.

## 🛠️ Tecnologias Utilizadas
* **Linguagem**: Python 3.12

* **Framework Bot**: discord.py

* **Banco de Dados*: SQLite (via aiosqlite)

* **APIs Externas**:

  * TMDB (The Movie Database) para metadados de mídias.

  * Google Gemini (google-genai) para resumos de inteligência artificial.

## ⚙️ Instalação e Configuração
## 1. Clone o repositório
Bash
git clone https://github.com/Golem8411/Archivist.git
cd Archivist

## 2. Instale as dependências
Certifique-se de estar usando um ambiente virtual e instale as bibliotecas necessárias:

Bash
pip install discord.py aiohttp python-dotenv aiosqlite google-genai

## 3. Configuração do Arquivo .env (Muito Importante)
Para que o bot funcione corretamente, ele precisa de chaves de autenticação privadas que não devem ser enviadas para o GitHub.

Crie um arquivo chamado exatamente .env na pasta raiz do projeto (mesma pasta do director.py) e adicione as seguintes variáveis:

DISCORD_TOKEN=cole_aqui_o_token_do_seu_bot_do_discord
TMDB_API_KEY=cole_aqui_sua_chave_da_api_do_tmdb
GEMINI_API_KEY=cole_aqui_sua_chave_do_google_ai_studio

Nota: O banco de dados golem_filmes.db será gerado automaticamente na mesma pasta assim que o bot for iniciado pela primeira vez.

## 4. Iniciando o Bot
Bash
python director.py

## 🚀 Funcionalidades e Comandos
Abaixo estão os comandos Slash disponíveis no bot.

## 🔍 Registrar Mídia (/vi)
Busca filmes ou séries diretamente do banco do TMDB.

Traz menus suspensos interativos para selecionar o resultado correto.

Se for uma série, puxa automaticamente a lista de temporadas para seleção.

Pede uma nota (0 a 10) e gera um "Card" embed lindão no chat com pôster, diretor, gêneros e data de lançamento.

Salva tudo no banco de dados do usuário.

<img width="456" height="181" alt="image" src="https://github.com/user-attachments/assets/a53bf00d-6797-41ca-b3bc-cfddcbc57601" />


<img width="558" height="348" alt="image" src="https://github.com/user-attachments/assets/647b99f6-166a-449f-b24f-1eb03f9fee0d" />


## 📜 Histórico Recente (/minhalista)
Mostra de forma rápida e privada (mensagem efêmera) as últimas 25 obras que o usuário registrou no banco de dados.

Exibe a data de quando foi assistido, a nota dada e a temporada (se aplicável).

<img width="424" height="317" alt="image" src="https://github.com/user-attachments/assets/d7709ec8-0d87-410f-9368-97ce1b5d39d2" />


## 📊 Exportar Dados (/exportar)
Gera um arquivo .csv formatado contendo todo o histórico de filmes e séries assistidos pelo usuário.

Filtro Opcional: O usuário pode digitar um ano específico (ex: 2024) para exportar apenas as obras assistidas naquele ano. Se deixado em branco, exporta a vida inteira.

O bot envia o arquivo diretamente no chat pronto para ser aberto no Excel ou Google Sheets.

<img width="747" height="289" alt="image" src="https://github.com/user-attachments/assets/041dd315-23c3-485c-97c8-90f2ec2424b1" />

## 🧠 Resumo Inteligente (/resumir)
Lê o histórico recente de mensagens (últimas 24 horas) do canal atual e envia tudo para a IA do Google Gemini.

## 🏗️ Arquitetura do Projeto

Este projeto foi refatorado para utilizar as melhores práticas de Engenharia de Software, abandonando o modelo monolítico. 
* **Padrão DAO (Data Access Object):** A lógica de banco de dados (`database.py`) é totalmente isolada da regra de negócios do bot, facilitando manutenção e testes.
* **Módulos (Cogs):** A arquitetura do Discord.py foi dividida em Cogs dinâmicos (pasta `cogs/`). O sistema principal carrega os comandos de mídia e inteligência artificial de forma independente.
* **Gestão de Sessões:** Uso eficiente de `aiohttp.ClientSession` persistente e atrelada à classe do bot, evitando vazamento de memória e múltiplas aberturas de conexão.

---

## 🐳 Executando com Docker (Recomendado)

O projeto está totalmente containerizado, garantindo que rode de forma idêntica em qualquer sistema operacional ou servidor em nuvem, sem conflitos de dependência.

### 1. Construa a Imagem Docker
Na pasta raiz do projeto, construa a imagem executando:
```bash
docker build -t golem-bot .

Ignora mensagens do próprio bot e comandos.

Focado em organizar sessões de brainstorming de histórias: ele extrai o sumo da discussão e categoriza (ex: Personagens, Enredo, Cenário) entregando um resumo estruturado no chat.
