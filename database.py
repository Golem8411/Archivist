import aiosqlite
import os
from datetime import datetime, timedelta, timezone

# Variável global para armazenar o caminho do banco de dados
DB_PATH = None

async def inicializar_banco(pasta_atual: str):
    global DB_PATH
    DB_PATH = os.path.join(pasta_atual, 'golem_filmes.db')
    
    async with aiosqlite.connect(DB_PATH) as conexao:
        # Tabela de Usuários
        await conexao.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id_discord TEXT PRIMARY KEY,
            tag_discord TEXT
        )
        ''')

        # Tabela de Mídias
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

        # Tabela de Histórico
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

async def registrar_no_banco(id_discord, tag_discord, id_tmdb, titulo_ingles, titulo_original, data_lancamento, sinopse, diretor, generos, temporada=None, nota=None):
    # Usando o padrão atualizado (timezone-aware)
    horario_brasilia = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
    
    async with aiosqlite.connect(DB_PATH) as conexao:
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
        
    async with aiosqlite.connect(DB_PATH) as conexao:
        async with conexao.execute(query, parametros) as cursor:
            resultados = await cursor.fetchall()
            return resultados

async def deletar_do_banco(id_registro):
    async with aiosqlite.connect(DB_PATH) as conexao:
        await conexao.execute('DELETE FROM historico WHERE id_registro = ?', (id_registro,))
        await conexao.commit()