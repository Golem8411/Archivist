import discord
from discord.ext import commands
from discord import app_commands # para o comandos /
import os
import aiohttp
from dotenv import load_dotenv
import sqlite3
import csv
import io
from datetime import datetime, timedelta
import aiosqlite
from google import genai

PASTA_ATUAL = os.path.dirname(os.path.abspath(__file__))
os.chdir(PASTA_ATUAL)

load_dotenv(os.path.join(PASTA_ATUAL, '.env'))
TOKEN = os.getenv('DISCORD_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DB_NAME = os.path.join(PASTA_ATUAL, 'golem_filmes.db')

cliente_gemini = genai.Client(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()

bot = commands.Bot(command_prefix='!', intents=intents)
sessao_web = None # Variável global para guardar a sessão

async def inicializar_banco():
    async with aiosqlite.connect(DB_NAME) as conexao:
        
        # 1. Tabela de Usuários
        await conexao.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id_discord TEXT PRIMARY KEY,
            tag_discord TEXT
        )
        ''')

        # 2. Tabela de Mídias
        await conexao.execute('''
        CREATE TABLE IF NOT EXISTS midias (
            id_tmdb INTEGER PRIMARY KEY,
            titulo_ingles TEXT,
            titulo_original TEXT,
            data_lancamento TEXT,
            sinopse TEXT,
            diretor TEXT,
            generos TEXT
        )
        ''')

        # 3. Tabela de Histórico
        await conexao.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id_registro INTEGER PRIMARY KEY AUTOINCREMENT,
            id_discord TEXT,
            id_tmdb INTEGER,
            temporada TEXT,
            nota INTEGER,
            data_hora_assistido TEXT,
            FOREIGN KEY(id_discord) REFERENCES usuarios(id_discord),
            FOREIGN KEY(id_tmdb) REFERENCES midias(id_tmdb)
        )
        ''')
        
        await conexao.commit()

@bot.event
async def on_ready():
    global sessao_web
    sessao_web = aiohttp.ClientSession()
    print('Sincronizando comandos Slash...')
    await bot.tree.sync() 
    print(f'Sucesso! {bot.user.name} online e pronto!')

@bot.event
async def on_ready():
    global sessao_web
    sessao_web = aiohttp.ClientSession()
    
    # Chama a criação do banco antes de liberar os comandos
    await inicializar_banco()
    print('Banco de dados inicializado/verificado com sucesso!')
    
    print('Sincronizando comandos Slash...')
    await bot.tree.sync() 
    print(f'Sucesso! {bot.user.name} online e pronto!')


async def registrar_no_banco(id_discord, tag_discord, id_tmdb, titulo_ingles, titulo_original, data_lancamento, sinopse, diretor, generos, temporada=None, nota=None):
    horario_brasilia = (datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
    
    async with aiosqlite.connect(DB_NAME) as conexao:
        await conexao.execute('''
        INSERT INTO usuarios (id_discord, tag_discord)
        VALUES (?, ?)
        ON CONFLICT(id_discord) DO UPDATE SET tag_discord = excluded.tag_discord
        ''', (str(id_discord), tag_discord))

        await conexao.execute('''
        INSERT OR IGNORE INTO midias (id_tmdb, titulo_ingles, titulo_original, data_lancamento, sinopse, diretor, generos)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (id_tmdb, titulo_ingles, titulo_original, data_lancamento, sinopse, diretor, generos))

        cursor = await conexao.execute('''
        INSERT INTO historico (id_discord, id_tmdb, temporada, nota, data_hora_assistido)
        VALUES (?, ?, ?, ?, ?)
        ''', (str(id_discord), id_tmdb, temporada, nota, horario_brasilia))

        id_registro = cursor.lastrowid 
        await conexao.commit()
            
    return id_registro 

async def buscar_historico(id_discord, limite=None, ano=None):
    query = '''
        SELECT h.id_registro, u.tag_discord, m.titulo_original, m.titulo_ingles, h.temporada, h.data_hora_assistido, h.nota, m.diretor, m.generos
        FROM historico h
        JOIN usuarios u ON h.id_discord = u.id_discord
        JOIN midias m ON h.id_tmdb = m.id_tmdb
        WHERE h.id_discord = ?
    '''
    parametros = [str(id_discord)]
    
    if ano:
        query += " AND h.data_hora_assistido LIKE ?"
        parametros.append(f"{ano}-%")
        
    query += " ORDER BY h.data_hora_assistido DESC"
    
    if limite:
        query += ' LIMIT ?'
        parametros.append(limite)
        
    async with aiosqlite.connect(DB_NAME) as conexao:
        async with conexao.execute(query, parametros) as cursor:
            resultados = await cursor.fetchall()
            return resultados

async def deletar_do_banco(id_registro):
    async with aiosqlite.connect(DB_NAME) as conexao:
        await conexao.execute('DELETE FROM historico WHERE id_registro = ?', (id_registro,))
        await conexao.close()

async def enviar_mensagem_final(interaction: discord.Interaction, texto_titulo: str, data_lancamento: str, sinopse: str, caminho_poster: str, id_registro: int, diretor: str, generos: str, nota: int = None):
    
    titulo_limpo = texto_titulo.replace("**", "")
    
    sinopse_segura = sinopse if sinopse and sinopse.strip() else "Sinopse não disponível para esta temporada."
    data_segura = data_lancamento if data_lancamento and data_lancamento.strip() else "Data indisponível"
    
    embed = discord.Embed(
        title=f"🎬 {titulo_limpo}",
        description=sinopse_segura,
        color=discord.Color.red()
    )
    
    embed.add_field(name="Lançamento", value=data_segura, inline=True)

    if diretor and diretor != "Desconhecido":
        embed.add_field(name="🎥 Diretor/Criador", value=diretor, inline=True)
    if generos and generos != "Desconhecido":
        embed.add_field(name="Gêneros", value=generos, inline=True)

    if nota is not None:
        embed.add_field(name="Nota", value=f"{nota}/10", inline=True)
        
    embed.add_field(name="Adicionado por", value=interaction.user.mention, inline=False)

    if caminho_poster:
        url_poster = f"https://image.tmdb.org/t/p/w500{caminho_poster}"
        embed.set_thumbnail(url=url_poster)
    
    view = ViewMensagemFinal(interaction.user.id, id_registro)
    
    await interaction.channel.send(embed=embed, view=view)

class ViewMensagemFinal(discord.ui.View):
    # Recebemos quem é o autor e qual é o ID da linha no banco
    def __init__(self, autor_id: int, id_registro: int):
        super().__init__(timeout=None)
        self.autor_id = autor_id
        self.id_registro = id_registro

    # Cria um botão vermelho de lixeira
    @discord.ui.button(label="Desfazer", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def botao_apagar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verifica se quem clicou foi o mesmo usuário que chamou o comando
        if interaction.user.id != self.autor_id:
            # Se for um curioso clicando, manda uma mensagem que só ele vê (ephemeral)
            await interaction.response.send_message("Apenas quem registrou o filme pode apagar essa mensagem!", ephemeral=True)
            return

        # Apaga do banco de dados usando o ID salvo
        await deletar_do_banco(self.id_registro)
        
        # Apaga a mensagem inteira do chat
        await interaction.message.delete()
    
# menu suspenso
class MenuMidia(discord.ui.Select):
    def __init__(self, lista_resultados):

        resultados_validos = [item for item in lista_resultados if item.get('media_type') in ['movie', 'tv']]

        self.filmes_dict = {item['id']: item for item in resultados_validos[:25]}
        opcoes = []
        
        # pega os 25 primeiros filmes da busca (25 é o max)
        for item in self.filmes_dict.values(): 
            if item['media_type'] == 'movie':
                titulo = item.get('title', 'Sem título')[:100]
                ano = item.get('release_date', '????')[:4]
                tipo_emoji = "🎬"
            else:
                titulo = item.get('name', 'Sem título')[:100]
                ano = item.get('first_air_date', '????')[:4]
                tipo_emoji = "📺"
                
            sinopse = item.get('overview', 'Sem sinopse')
            
            texto_descricao = f"[{ano}] {tipo_emoji} | {sinopse}"
            
            if len(texto_descricao) > 100:
                descricao = texto_descricao[:97] + '...'
            else:
                descricao = texto_descricao 
                           
            opcoes.append(discord.SelectOption(label=titulo, description=descricao, value=str(item['id'])))
        super().__init__(placeholder="Selecione o que você assistiu", min_values=1, max_values=1, options=opcoes)

    # Essa função roda quando o usuário clica em uma opção do menu principal
    async def callback(self, interaction: discord.Interaction):
        item_id_escolhido = int(self.values[0])
        item_escolhido = self.filmes_dict[item_id_escolhido]       

        # SE FOR FILME
        if item_escolhido['media_type'] == 'movie':
            await interaction.response.edit_message(content="Buscando detalhes do filme...", view=None)

            url_detalhes = f"https://api.themoviedb.org/3/movie/{item_id_escolhido}"
            param_detalhes = {"api_key": TMDB_API_KEY, "language": "en-US", "append_to_response": "credits"}

            async with sessao_web.get(url_detalhes, params=param_detalhes) as resp:
                if resp.status == 200:
                    detalhes = await resp.json()
                    generos = ", ".join([g['name'] for g in detalhes.get('genres', [])])
                    equipe = detalhes.get('credits', {}).get('crew', [])
                    diretor = next((m['name'] for m in equipe if m['job'] == 'Director'), "Desconhecido")
                else:
                    generos, diretor = "Desconhecido", "Desconhecido"

            titulo = item_escolhido.get('title', 'Titulo indisponivel')
            titulo_original = item_escolhido.get('original_title', 'Título indisponível')
            data_lancamento = item_escolhido.get('release_date', 'Data indisponível')
            texto_titulo = f"**{titulo_original}** ({titulo})" if titulo_original != titulo else f"**{titulo_original}**"
            sinopse = item_escolhido.get('overview', 'Sinopse indisponivel')
            caminho_poster = item_escolhido.get('poster_path')


            dados_midia = {
                'id_tmdb': item_id_escolhido,
                'titulo_ingles': titulo,
                'titulo_original': titulo_original,
                'data_lancamento': data_lancamento,
                'sinopse': sinopse,
                'temporada': None,
                'texto_titulo': texto_titulo,
                'caminho_poster': caminho_poster,
                'diretor': diretor,
                'generos': generos
            }
            
            view_nota = ViewNota(dados_midia)
            await interaction.edit_original_response(content="**Pronto! Agora escolha a sua nota:**", view=view_nota)
            
        # SE FOR SÉRIE (Chama o segundo menu)
        else:
            await interaction.response.edit_message(content="Buscando temporadas...", view=None)
            
            url_tv = f"https://api.themoviedb.org/3/tv/{item_id_escolhido}"
            parametros = {"api_key": TMDB_API_KEY, "language": "en-US", "append_to_response": "credits"}
            
            async with sessao_web.get(url_tv, params=parametros) as response:
                if response.status == 200:
                    dados = await response.json()
                    temporadas = dados.get('seasons', [])

                    generos = ", ".join([g['name'] for g in dados.get('genres', [])])
                    criadores = dados.get('created_by', [])
                    diretor = ", ".join([c['name'] for c in criadores]) if criadores else "Desconhecido"
                        
                    if not temporadas:
                        await interaction.edit_original_response("Nenhuma temporada encontrada.", ephemeral=True)
                        return
                            
                    view = ViewTemporada(item_escolhido, temporadas, diretor, generos)
                    await interaction.edit_original_response("Qual temporada você assistiu?", view=view, ephemeral=True)
                else:
                    await interaction.edit_original_response(f"Erro na API! Código: {response.status}", ephemeral=True)
# a caixa que segura o menu
class ViewMidia(discord.ui.View):
    def __init__(self, lista_resultados):
        super().__init__(timeout=60)
        self.add_item(MenuMidia(lista_resultados))

class MenuTemporada(discord.ui.Select):
    def __init__(self, item_escolhido, temporadas, diretor, generos):
        self.item_escolhido = item_escolhido
        self.temporadas = temporadas[:25]
        self.diretor = diretor
        self.generos = generos
        
        opcoes = []
        for temp in self.temporadas:
            nome_temp = temp.get('name', 'Temporada Desconhecida')
            episodios = temp.get('episode_count', 0)
            valor_id = str(temp.get('season_number', 0))
            opcoes.append(discord.SelectOption(label=nome_temp[:100], description=f"{episodios} episódios", value=valor_id))
            
        super().__init__(placeholder="Qual temporada você assistiu?", min_values=1, max_values=1, options=opcoes)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Processando...", view=None)
        numero_temporada = int(self.values[0])
        temporada_escolhida = next((t for t in self.temporadas if t.get('season_number') == numero_temporada), {})
        
        titulo = self.item_escolhido.get('name', 'Título indisponível')
        titulo_original = self.item_escolhido.get('original_name', 'Título indisponível')
        texto_titulo = f"**{titulo_original}** ({titulo})" if titulo_original != titulo else f"**{titulo_original}**"
          
        nome_temporada = temporada_escolhida.get('name', f'Temporada {numero_temporada}')
        texto_completo = f"{texto_titulo} - {nome_temporada}"
        
        data_lancamento = temporada_escolhida.get('air_date') or self.item_escolhido.get('first_air_date') or 'Data indisponível'
        sinopse = temporada_escolhida.get('overview') or self.item_escolhido.get('overview') or 'Sinopse indisponível'
        caminho_poster = temporada_escolhida.get('poster_path') or self.item_escolhido.get('poster_path')

        dados_midia = {
            'id_tmdb': self.item_escolhido.get('id'),
            'titulo_ingles': titulo,
            'titulo_original': titulo_original,
            'data_lancamento': data_lancamento,
            'sinopse': sinopse,
            'temporada': nome_temporada,
            'texto_titulo': texto_completo,
            'caminho_poster': caminho_poster,
            'diretor': self.diretor,
            'generos': self.generos
        }
        
        view_nota = ViewNota(dados_midia)
        await interaction.edit_original_response(content="**Pronto! Agora escolha a sua nota para esta temporada:**", view=view_nota)

class ViewTemporada(discord.ui.View):
    def __init__(self, item_escolhido, temporadas, diretor, generos):
        super().__init__(timeout=60)
        self.add_item(MenuTemporada(item_escolhido, temporadas, diretor, generos))

class MenuMinhaLista(discord.ui.Select):
    def __init__(self, resultados):
        self.resultados_dict = {str(linha[0]): linha for linha in resultados}
        opcoes = []
        
        for linha in resultados:
            id_registro, tag_usuario, titulo_original, titulo_ingles, temporada, data_hora, nota, diretor, generos = linha
            
            # Monta o título
            nome_exibicao = titulo_ingles
            if temporada:
                nome_exibicao += f" ({temporada})"
                
            # Formata a data ('YYYY-MM-DD HH:MM:SS')
            data_curta = data_hora.split()[0]
            # Converte de YYYY-MM-DD para DD/MM/YYYY
            partes_data = data_curta.split('-')
            data_formatada = f"{partes_data[2]}/{partes_data[1]}/{partes_data[0]}" if len(partes_data) == 3 else data_curta
            
            # Mostra a nota se ela existir
            if nota is not None:
                descricao = f"Nota: {nota}/10 ⭐ | Em: {data_formatada}"
            else:
                descricao = f"Assistido em: {data_formatada}"
            
            # Cria a opção do menu
            opcoes.append(discord.SelectOption(
                label=nome_exibicao[:100], 
                description=descricao[:100], 
                value=str(id_registro),
                emoji="🍿"
            ))
            
        super().__init__(placeholder="Veja o que você já assistiu", min_values=1, max_values=1, options=opcoes)

    # Quando o usuário clica num item da própria lista
    async def callback(self, interaction: discord.Interaction):
        linha_escolhida = self.resultados_dict[self.values[0]]
        titulo = linha_escolhida[2]
        temporada = linha_escolhida[4]
        nota = linha_escolhida[6]
        
        mensagem = f"Você assistiu **{titulo}**"
        if temporada:
            mensagem += f" - {temporada}"
        if nota is not None:
            mensagem += f" e deu nota **{nota}/10**!"
                    
        # Apenas avisa o que ele selecionou (como é só visualização, não precisamos fazer mais nada)
        await interaction.response.send_message(mensagem, ephemeral=True)

class ViewMinhaLista(discord.ui.View):
    def __init__(self, resultados):
        super().__init__(timeout=60)
        self.add_item(MenuMinhaLista(resultados))

class MenuNota(discord.ui.Select):
    def __init__(self, dados_midia):
        self.dados_midia = dados_midia 
        
        # Cria a lista de opções: Pular e Notas de 10 a 0
        opcoes = [discord.SelectOption(label="Sem nota (Pular)", value="None", emoji="⏭️")]
        for i in range(10, -1, -1):
            opcoes.append(discord.SelectOption(label=f"Nota {i}/10", value=str(i), emoji="⭐"))
            
        super().__init__(placeholder="Que nota você dá?", min_values=1, max_values=1, options=opcoes)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Salvando no banco de dados...", view=None)
        
        # Verifica se o usuário pulou ou deu nota
        valor_escolhido = self.values[0]
        nota_final = int(valor_escolhido) if valor_escolhido != "None" else None
        
        # Puxa os dados do menu anterior
        dados = self.dados_midia
        
        # salva no banco de dados
        id_registro = await registrar_no_banco(
            id_discord=interaction.user.id,
            tag_discord=str(interaction.user),
            id_tmdb=dados['id_tmdb'],
            titulo_ingles=dados['titulo_ingles'],
            titulo_original=dados['titulo_original'],
            data_lancamento=dados['data_lancamento'],
            sinopse=dados['sinopse'],
            diretor=dados['diretor'],
            generos=dados['generos'],
            temporada=dados['temporada'],
            nota=nota_final
        )
        
        await enviar_mensagem_final(
            interaction, 
            dados['texto_titulo'], 
            dados['data_lancamento'], 
            dados['sinopse'], 
            dados['caminho_poster'], 
            id_registro,
            dados['diretor'],
            dados['generos'],
            nota_final
        )

        await interaction.delete_original_response()

class ViewNota(discord.ui.View):
    def __init__(self, dados_midia):
        super().__init__(timeout=60)
        self.add_item(MenuNota(dados_midia))

# comando Slash
@bot.tree.command(name="vi", description="Busca um filme ou série e adiciona à sua lista")
@app_commands.describe(nome_da_midia="O nome do filme que você assistiu")
async def vi(interaction: discord.Interaction, nome_da_midia: str):
    
    # 'defer' garante que não vai ter timeout
    # o ephemeral=True garante que só o usuário vai ver isso
    await interaction.response.defer(ephemeral=True)

    url = f"https://api.themoviedb.org/3/search/multi"

    parametros = {
        "api_key": TMDB_API_KEY,
        "query": nome_da_midia,
        "language": "en-US"
    }
    async with sessao_web.get(url, params=parametros) as response:
        if response.status == 200:
            dados = await response.json()
            resultados = dados.get('results', [])
                
            if not resultados:
                await interaction.followup.send("Nenhum resultado encontrado com esse nome.", ephemeral=True)
                return

            view = ViewMidia(resultados)
            await interaction.followup.send(f"Encontrei alguns resultados para **{nome_da_midia}**:", view=view, ephemeral=True)
        else:
            await interaction.followup.send(f"Erro na API! Código: {response.status}", ephemeral=True)

@bot.tree.command(name="minhalista", description="Mostra as últimas 25 mídias que você assistiu")
async def minhalista(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    # Chama a função passando o ID do usuário que digitou o comando
    resultados = await buscar_historico(interaction.user.id, limite=25)
    
    # Se a lista voltar vazia
    if not resultados:
        await interaction.followup.send("Sua lista está vazia! Use o comando `/vi` para registrar algum filme ou série primeiro.", ephemeral=True)
        return
        
    # Se tiver resultados, monta o menu e envia
    view = ViewMinhaLista(resultados)
    await interaction.followup.send("Aqui estão seus últimos 25 registros:", view=view, ephemeral=True)

@bot.tree.command(name="exportar", description="Gera um arquivo CSV com o seu histórico de mídias")
@app_commands.describe(ano="Opcional: Digite o ano para filtrar (ex: 2024). Deixe em branco para exportar tudo.")
async def exportar(interaction: discord.Interaction, ano: int = None):
    await interaction.response.defer(ephemeral=True)
    
    # Passamos o ano para a nossa função de busca
    resultados = await buscar_historico(interaction.user.id, ano=ano)
    
    if not resultados:
        if ano:
            await interaction.followup.send(f"Nenhum registro encontrado para o ano de **{ano}**.", ephemeral=True)
        else:
            await interaction.followup.send("A sua lista ainda está vazia! Registre algo com o `/vi` primeiro.", ephemeral=True)
        return
        
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    
    # Cabeçalho atualizado
    escritor.writerow(['Usuário', 'Título Original', 'Título Inglês', 'Temporada', 'Nota', 'Data Registrado', 'Diretor', 'Gêneros'])
    
    for linha in resultados:
        id_registro, tag_usuario, titulo_original, titulo_ingles, temporada, data_hora, nota, diretor, generos = linha
        
        texto_temporada = temporada if temporada else "-"
        texto_nota = nota if nota is not None else "-"
        
        escritor.writerow([tag_usuario, titulo_original, titulo_ingles, texto_temporada, texto_nota, data_hora, diretor, generos])
        
    buffer.seek(0) 
    arquivo_bytes = io.BytesIO(buffer.getvalue().encode('utf-8')) 
    
    # Nome do arquivo dinâmico
    if ano:
        nome_arquivo = f"historico_{interaction.user.name}_{ano}.csv"
        mensagem_final = f"📊 Pronto! Aqui está o seu relatório do ano **{ano}**:"
    else:
        nome_arquivo = f"historico_{interaction.user.name}_completo.csv"
        mensagem_final = "📊 Pronto! Aqui está o seu relatório completo:"
        
    arquivo_discord = discord.File(arquivo_bytes, filename=nome_arquivo)
    
    await interaction.followup.send(mensagem_final, file=arquivo_discord, ephemeral=True)

@bot.tree.command(name="resumir", description="Lê as discussões e notas do dia neste canal e cria um resumo organizado com IA")
async def resumir(interaction: discord.Interaction):
    # O bot avisa que está "pensando"
    await interaction.response.defer()
    
    # Define o limite de tempo (ex: últimas 24 horas)
    limite_tempo = discord.utils.utcnow() - timedelta(hours=24)
    
    textos = []
    
    # Puxa até 100 mensagens do canal atual que foram enviadas depois do limite_tempo
    async for msg in interaction.channel.history(limit=100, after=limite_tempo, oldest_first=True):
        # Ignora comandos de bot e mensagens vazias
        if not msg.author.bot and msg.content.strip(): 
            # Formata com o nome do usuário para a IA entender quem disse o quê numa discussão
            textos.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author.display_name}: {msg.content}")
            
    if not textos:
        await interaction.followup.send("Não encontrei nenhuma anotação ou conversa válida nas últimas 24 horas neste canal.")
        return
        
    texto_completo = "\n".join(textos)
    
    prompt = (
        "Você é um assistente criativo focado em organizar anotações e brainstorming de histórias. "
        "Abaixo está um histórico de mensagens de um chat onde o autor enviou várias notas e ideias soltas, "
        "e possivelmente discutiu algumas delas, ao longo do dia."
        "Seu trabalho é ler tudo, extrair o sumo das ideias e criar um resumo estruturado para o autor organizar depois. "
        "Se aplicável, categorize as informações (ex: 'Desenvolvimento de Personagens', 'Pontos de Enredo', 'Regras do Mundo/Construção de Cenário', 'Tarefas Pendentes'). "
        "Seja claro, conciso e use formatação em markdown (negritos, listas).\n\n"
        f"Histórico do Chat:\n{texto_completo}"
    )
    
    try:

        # Usa o novo cliente para gerar o conteúdo com o modelo escolhido
        resposta = cliente_gemini.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt
        )
        
        texto_resumo = resposta.text
     
        if len(texto_resumo) > 4096:
            texto_resumo = texto_resumo[:4093] + "..."
            
        embed = discord.Embed(
            title="Resumo das Ideias do Dia",
            description=texto_resumo,
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Resumo gerado analisando {len(textos)} mensagens.")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"Ocorreu um erro ao gerar o resumo: {e}")

bot.run(TOKEN)