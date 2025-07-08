import discord
import requests
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import asyncio
import os

# Use variáveis de ambiente seguras no Replit
TOKEN = os.getenv("DISCORD_TOKEN")  # Configure isso no Secrets do Replit
CANAL_ID = 1391782013568290858
ROLE_ID = "1391784968786808873"

URL = "https://animesbr.tv"
HEADERS = {"User-Agent": "Mozilla/5.0"}
ultimo_postado = ""

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def get_ultimo_episodio():
    r = requests.get(URL, headers=HEADERS)
    soup = BeautifulSoup(r.text, 'html.parser')

    primeiro = soup.find('article', class_='item se episodes')
    if not primeiro:
        return None

    data_div = primeiro.find('div', class_='data')
    a_tag = data_div.find('h3').find('a') if data_div else None
    link = a_tag['href'] if a_tag else None
    titulo_ep = a_tag.get_text(strip=True) if a_tag else "Episódio"

    nome_anime_tag = data_div.find('span', class_='serie') if data_div else None
    nome_anime = nome_anime_tag.get_text(strip=True) if nome_anime_tag else "Novo Anime"

    qualidade_tag = primeiro.find('span', class_='quality')
    qualidade = qualidade_tag.get_text(strip=True) if qualidade_tag else "Desconhecida"

    spans = data_div.find_all('span') if data_div else []
    data = spans[0].get_text(strip=True) if spans else "Data não disponível"

    poster_div = primeiro.find('div', class_='poster')
    img_tag = poster_div.find('img') if poster_div else None
    imagem_url = img_tag['src'] if img_tag else None

    return {
        "link": link,
        "titulo_ep": titulo_ep,
        "nome_anime": nome_anime,
        "qualidade": qualidade,
        "data": data,
        "imagem": imagem_url
    }

async def checar_novos_episodios():
    global ultimo_postado
    await client.wait_until_ready()
    canal = client.get_channel(CANAL_ID)

    while not client.is_closed():
        try:
            ep = get_ultimo_episodio()
            if ep and ep["link"] != ultimo_postado:
                ultimo_postado = ep["link"]

                embed = discord.Embed(
                    title=f"{ep['nome_anime']} - {ep['titulo_ep']}",
                    description=f"**Tipo:** {ep['qualidade']}\n[👉 Assistir online]({ep['link']})",
                    color=0x9c27b0
                )
                embed.set_footer(text=f"Animesbr.tv • {ep['data']}",
                                 icon_url="https://cdn.discordapp.com/emojis/1391789271471624233.webp?size=96&quality=lossless")

                if ep['imagem']:
                    embed.set_thumbnail(url=ep['imagem'])  # ou set_image para imagem maior

                await canal.send(
                    content=f"<@&{ROLE_ID}>",
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(roles=True),
                    suppress_embeds=False
                )
        except Exception as e:
            print("Erro ao buscar episódio:", e)

        await asyncio.sleep(600)

@client.event
async def on_ready():
    print(f"Bot online como {client.user}")
    client.loop.create_task(checar_novos_episodios())

app = Flask('')

@app.route('/')
def home():
    return "Bot ativo!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Adicione isso antes de client.run(TOKEN)
keep_alive()

client.run(TOKEN)
