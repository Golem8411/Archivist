import discord
from discord.ext import commands
from discord import app_commands
import os
from datetime import timedelta
from google import genai

# Inicializa o cliente do Gemini usando a nova biblioteca google-genai
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
cliente_gemini = genai.Client(api_key=GEMINI_API_KEY)

class InteligenciaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="resumir", description="Lê as discussões e notas do dia neste canal e cria um resumo organizado com IA")
    async def resumir(self, interaction: discord.Interaction):
        # defer() avisa ao Discord que a resposta pode demorar mais de 3 segundos
        await interaction.response.defer()
        
        limite_tempo = discord.utils.utcnow() - timedelta(hours=24)
        textos = []
        
        # Lê o histórico do canal (limitado a 100 mensagens para economizar tokens/tempo)
        async for msg in interaction.channel.history(limit=100, after=limite_tempo, oldest_first=True):
            if not msg.author.bot and msg.content.strip(): 
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
            # Geração com a API atualizada
            resposta = cliente_gemini.models.generate_content(
                model='gemini-flash-latest',
                contents=prompt
            )
            
            texto_resumo = resposta.text
         
            # Proteção contra o limite de caracteres do Embed do Discord (4096 max)
            if len(texto_resumo) > 4096:
                texto_resumo = texto_resumo[:4093] + "..."
                
            embed = discord.Embed(
                title="🧠 Resumo das Ideias do Dia",
                description=texto_resumo,
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"Resumo gerado analisando {len(textos)} mensagens.")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Ocorreu um erro ao gerar o resumo: {e}")

async def setup(bot):
    await bot.add_cog(InteligenciaCog(bot))