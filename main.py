import discord
from discord.ext import commands
import os
import aiohttp
from dotenv import load_dotenv

import database

# Configuração de ambiente
PASTA_ATUAL = os.path.dirname(os.path.abspath(__file__))
os.chdir(PASTA_ATUAL)
load_dotenv(os.path.join(PASTA_ATUAL, '.env'))

TOKEN = os.getenv('DISCORD_TOKEN')

class GolemBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=discord.Intents.default())
        
        self.sessao_web = None 

    async def setup_hook(self):
        
        # Instancia a sessão web persistente
        self.sessao_web = aiohttp.ClientSession()

        # Inicializa e valida o banco de dados
        await database.inicializar_banco(PASTA_ATUAL)
        print("Banco de dados sincronizado e validado.")

        # Varre a pasta 'cogs' e carrega os módulos dinamicamente
        if not os.path.exists('./cogs'):
            os.makedirs('./cogs')
            
        for arquivo in os.listdir('./cogs'):
            if arquivo.endswith('.py'):
                await self.load_extension(f'cogs.{arquivo[:-3]}')
                print(f'Módulo carregado: {arquivo}')

    # Destrutor seguro para fechar conexões HTTP abertas
    async def close(self):
        if self.sessao_web:
            await self.sessao_web.close()
        await super().close()

    # Evento disparado quando a conexão com o Discord é estabelecida
    async def on_ready(self):
        print('Sincronizando comandos Slash...')
        await self.tree.sync()
        print(f'Sucesso! {self.user.name} online!')

if __name__ == '__main__':
    # Instancia e roda o bot
    bot = GolemBot()
    bot.run(TOKEN)