import discord
from discord.ext import commands
from discord import app_commands
import os
import csv
import io

import database

TMDB_API_KEY = os.getenv('TMDB_API_KEY')

# FUNÇÕES AUXILIARES E VIEWS (UI)
async def enviar_mensagem_final(interaction: discord.Interaction, texto_titulo: str, data_lancamento: str, sinopse: str, caminho_poster: str, id_registro: int, diretor: str, generos: str, nota: int = None):
    titulo_limpo = texto_titulo.replace("**", "")
    sinopse_segura = sinopse if sinopse and sinopse.strip() else "Sinopse não disponível."
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
    def __init__(self, autor_id: int, id_registro: int):
        super().__init__(timeout=None)
        self.autor_id = autor_id
        self.id_registro = id_registro

    @discord.ui.button(label="Desfazer", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def botao_apagar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("Apenas quem registrou o filme pode apagar essa mensagem!", ephemeral=True)
            return

        await database.deletar_do_banco(self.id_registro)
        await interaction.message.delete()

class MenuMidia(discord.ui.Select):
    def __init__(self, lista_resultados):
        resultados_validos = [item for item in lista_resultados if item.get('media_type') in ['movie', 'tv']]
        self.filmes_dict = {item['id']: item for item in resultados_validos[:25]}
        opcoes = []
        
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
            descricao = texto_descricao[:97] + '...' if len(texto_descricao) > 100 else texto_descricao 
            opcoes.append(discord.SelectOption(label=titulo, description=descricao, value=str(item['id'])))
            
        super().__init__(placeholder="Selecione o que você assistiu", min_values=1, max_values=1, options=opcoes)

    async def callback(self, interaction: discord.Interaction):
        item_id_escolhido = int(self.values[0])
        item_escolhido = self.filmes_dict[item_id_escolhido]       
        sessao_web = interaction.client.sessao_web # Acessa a sessão da classe principal

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
                        await interaction.edit_original_response(content="Nenhuma temporada encontrada.", view=None)
                        return
                            
                    view = ViewTemporada(item_escolhido, temporadas, diretor, generos)
                    # Utilizando a técnica de mensagem efêmera limpa
                    await interaction.edit_original_response(content="Qual temporada você assistiu?", view=view)
                else:
                    await interaction.edit_original_response(content=f"Erro na API! Código: {response.status}", view=None)

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
        
        # Cadeia de operadores or para evitar strings vazias "" no banco e embed
        data_lancamento = temporada_escolhida.get('air_date') or self.item_escolhido.get('first_air_date') or "Data indisponível"
        sinopse = temporada_escolhida.get('overview') or self.item_escolhido.get('overview') or "Sinopse indisponível."
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
            nome_exibicao = titulo_ingles
            if temporada:
                nome_exibicao += f" ({temporada})"
                
            data_curta = data_hora.split()[0]
            partes_data = data_curta.split('-')
            data_formatada = f"{partes_data[2]}/{partes_data[1]}/{partes_data[0]}" if len(partes_data) == 3 else data_curta
            
            descricao = f"Nota: {nota}/10 ⭐ | Em: {data_formatada}" if nota is not None else f"Assistido em: {data_formatada}"
            opcoes.append(discord.SelectOption(label=nome_exibicao[:100], description=descricao[:100], value=str(id_registro), emoji="🍿"))
            
        super().__init__(placeholder="Veja o que você já assistiu", min_values=1, max_values=1, options=opcoes)

    async def callback(self, interaction: discord.Interaction):
        linha_escolhida = self.resultados_dict[self.values[0]]
        titulo = linha_escolhida[2]
        temporada = linha_escolhida[4]
        nota = linha_escolhida[6]
        
        mensagem = f"Você assistiu **{titulo}**"
        if temporada: mensagem += f" - {temporada}"
        if nota is not None: mensagem += f" e deu nota **{nota}/10**!"
                    
        await interaction.response.send_message(mensagem, ephemeral=True)

class ViewMinhaLista(discord.ui.View):
    def __init__(self, resultados):
        super().__init__(timeout=60)
        self.add_item(MenuMinhaLista(resultados))

class MenuNota(discord.ui.Select):
    def __init__(self, dados_midia):
        self.dados_midia = dados_midia 
        opcoes = [discord.SelectOption(label="Sem nota (Pular)", value="None", emoji="⏭️")]
        for i in range(10, -1, -1):
            opcoes.append(discord.SelectOption(label=f"Nota {i}/10", value=str(i), emoji="⭐"))
        super().__init__(placeholder="Que nota você dá?", min_values=1, max_values=1, options=opcoes)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Salvando no banco de dados...", view=None)
        
        valor_escolhido = self.values[0]
        nota_final = int(valor_escolhido) if valor_escolhido != "None" else None
        dados = self.dados_midia
        
        # Comunicação com a camada de banco de dados
        id_registro = await database.registrar_no_banco(
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


# CLASSE COG (MÓDULO PRINCIPAL DE COMANDOS)

class MidiasCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="vi", description="Busca um filme ou série e adiciona à sua lista")
    @app_commands.describe(nome_da_midia="O nome do filme que você assistiu")
    async def vi(self, interaction: discord.Interaction, nome_da_midia: str):
        await interaction.response.defer(ephemeral=True)
        url = f"https://api.themoviedb.org/3/search/multi"
        parametros = {"api_key": TMDB_API_KEY, "query": nome_da_midia, "language": "en-US"}
        
        async with self.bot.sessao_web.get(url, params=parametros) as response:
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

    @app_commands.command(name="minhalista", description="Mostra as últimas 25 mídias que você assistiu")
    async def minhalista(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        resultados = await database.buscar_historico(interaction.user.id, limite=25)
        
        if not resultados:
            await interaction.followup.send("Sua lista está vazia! Use o comando `/vi` primeiro.", ephemeral=True)
            return
            
        view = ViewMinhaLista(resultados)
        await interaction.followup.send("Aqui estão seus últimos 25 registros:", view=view, ephemeral=True)

    @app_commands.command(name="exportar", description="Gera um arquivo CSV com o seu histórico de mídias")
    @app_commands.describe(ano="Opcional: Digite o ano para filtrar (ex: 2024). Deixe em branco para exportar tudo.")
    async def exportar(self, interaction: discord.Interaction, ano: int = None):
        await interaction.response.defer(ephemeral=True)
        resultados = await database.buscar_historico(interaction.user.id, ano=ano)
        
        if not resultados:
            msg = f"Nenhum registro encontrado para o ano de **{ano}**." if ano else "A sua lista ainda está vazia!"
            await interaction.followup.send(msg, ephemeral=True)
            return
            
        buffer = io.StringIO()
        escritor = csv.writer(buffer)
        escritor.writerow(['Usuário', 'Título Original', 'Título Inglês', 'Temporada', 'Nota', 'Data Registrado', 'Diretor', 'Gêneros'])
        
        for linha in resultados:
            id_registro, tag_usuario, titulo_original, titulo_ingles, temporada, data_hora, nota, diretor, generos = linha
            texto_temporada = temporada if temporada else "-"
            texto_nota = nota if nota is not None else "-"
            escritor.writerow([tag_usuario, titulo_original, titulo_ingles, texto_temporada, texto_nota, data_hora, diretor, generos])
            
        buffer.seek(0) 
        arquivo_bytes = io.BytesIO(buffer.getvalue().encode('utf-8')) 
        
        nome_arquivo = f"historico_{interaction.user.name}_{ano}.csv" if ano else f"historico_{interaction.user.name}_completo.csv"
        mensagem_final = f"📊 Pronto! Aqui está o seu relatório do ano **{ano}**:" if ano else "📊 Pronto! Aqui está o seu relatório completo:"
            
        arquivo_discord = discord.File(arquivo_bytes, filename=nome_arquivo)
        await interaction.followup.send(mensagem_final, file=arquivo_discord, ephemeral=True)

# Função para o main.py carregar este arquivo
async def setup(bot):
    await bot.add_cog(MidiasCog(bot))