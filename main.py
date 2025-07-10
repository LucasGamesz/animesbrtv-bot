import discord
import requests
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import asyncio
import os
import asyncpg

TOKEN = os.getenv("DISCORD_TOKEN")
CANAL_ID = 1391782013568290858
ROLE_ID = "1391784968786808873"
DB_URL = os.getenv("DATABASE_URL")

URL = "https://animesbr.tv"
HEADERS = {"User-Agent": "Mozilla/5.0"}

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# Conecta ao PostgreSQL
async def conectar_banco():
    return await asyncpg.connect(DB_URL)

# Verifica se o link já foi postado
async def episodio_ja_postado(conn, link):
    row = await conn.fetchrow("SELECT 1 FROM episodios_postados WHERE link = $1", link)
    return row is not None

# Salva o link do episódio no banco
async def salvar_episodio(conn, link):
    await conn.execute("INSERT INTO episodios_postados (link) VALUES ($1)", link)

# Raspa os episódios mais recentes
def get_ultimos_episodios(limit=5):
    r = requests.get(URL, headers=HEADERS)
    soup = BeautifulSoup(r.text, 'html.parser')
    episodios = []

    artigos = soup.select('article.item.se.episodes')[:limit]
    for artigo in artigos:
        data_div = artigo.find('div', class_='data')
        a_tag = data_div.find('h3').find('a') if data_div else None
        link = a_tag['href'] if a_tag else None
        titulo_ep = a_tag.get_text(strip=True) if a_tag else "Episódio"

        nome_anime_tag = data_div.find('span', class_='serie') if data_div else None
        nome_anime = nome_anime_tag.get_text(strip=True) if nome_anime_tag else "Novo Anime"

        qualidade_tag = artigo.find('span', class_='quality')
        qualidade = qualidade_tag.get_text(strip=True) if qualidade_tag else "Desconhecida"

        spans = data_div.find_all('span') if data_div else []
        data = spans[0].get_text(strip=True) if spans else "Data não disponível"

        poster_div = artigo.find('div', class_='poster')
        img_tag = poster_div.find('img') if poster_div else None
        imagem_url = img_tag['src'] if img_tag else None

        episodios.append({
            "link": link,
            "titulo_ep": titulo_ep,
            "nome_anime": nome_anime,
            "qualidade": qualidade,
            "data": data,
            "imagem": imagem_url
        })

    return episodios

# Loop principal que verifica e envia os episódios
async def checar_novos_episodios():
    await client.wait_until_ready()
    canal = client.get_channel(CANAL_ID)
    conn = await conectar_banco()

    while not client.is_closed():
        try:
            episodios = get_ultimos_episodios()
            
            # Posta todos os episódios novos, do mais antigo para o mais recente
            for ep in reversed(episodios):
                if ep["link"] and not await episodio_ja_postado(conn, ep["link"]):
                    await salvar_episodio(conn, ep["link"])
            
                    embed = discord.Embed(
                        title=f"{ep['nome_anime']} - {ep['titulo_ep']}",
                        description=f"**Tipo:** {ep['qualidade']}\n[👉 Assistir online]({ep['link']})",
                        color=0x9c27b0
                    )
                    embed.set_footer(
                        text=f"Animesbr.tv • {ep['data']}",
                        icon_url="https://cdn.discordapp.com/emojis/1391789271471624233.webp?size=96&quality=lossless"
                    )
                    if ep['imagem']:
                        embed.set_thumbnail(url=ep['imagem'])
            
                    await canal.send(
                        content=f"<@&{ROLE_ID}>",
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(roles=True),
                        suppress_embeds=False
                    )
        except Exception as e:
            print("Erro ao buscar episódios:", e)

        await asyncio.sleep(300)

@client.event
async def on_ready():
    print(f"Bot online como {client.user}")
    client.loop.create_task(checar_novos_episodios())

# Mantém Railway acordado
app = Flask('')

@app.route('/')
def home():
    return "Bot ativo!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()
client.run(TOKEN) 
