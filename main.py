import discord
from discord.ext import commands
import requests, certifi
from requests.exceptions import RequestException, Timeout
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import asyncio, os, asyncpg, datetime as dt

TOKEN     = os.getenv("DISCORD_TOKEN")
CANAL_ID  = 1391782013568290858
ROLE_ID   = "1391784968786808873"
DB_URL    = os.getenv("DATABASE_URL")

URL     = "https://animesbr.app"
HEADERS = {"User-Agent": "Mozilla/5.0"}

intents = discord.Intents.default()
bot     = commands.Bot(command_prefix="a!", intents=intents)

# ────────── PostgreSQL ──────────
async def conectar_banco():
    print("[DB] Conectando ao banco de dados...")
    conn = await asyncpg.connect(DB_URL)
    print("[DB] Conectado.")
    return conn

async def episodio_ja_postado(conn, link):
    registrado = await conn.fetchval("SELECT 1 FROM episodios_postados WHERE link = $1", link)
    print(f"[DB] Já postado? {'✅' if registrado else '❌'} → {link}")
    return registrado is not None

async def salvar_episodio(conn, link):
    print(f"[DB] Salvando novo episódio: {link}")
    await conn.execute("INSERT INTO episodios_postados (link) VALUES ($1)", link)

# ────────── Scraper ──────────
def get_ultimos_episodios(limit=5):
    print(f"[{dt.datetime.now():%H:%M:%S}] Buscando episódios do site...")
    try:
        r = requests.get(URL, headers=HEADERS, timeout=15, verify=certifi.where())
        r.raise_for_status()
    except (RequestException, Timeout) as e:
        print(f"[ERRO] Falha na requisição: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    artigos = soup.select('article.item.se.episodes')[:limit]
    print(f"[SCRAPER] {len(artigos)} episódios encontrados.")

    episodios = []
    for artigo in artigos:
        data_div   = artigo.find('div', class_='data')
        a_tag      = data_div.find('h3').find('a') if data_div else None
        link       = a_tag['href'] if a_tag else None
        titulo_ep  = a_tag.get_text(strip=True) if a_tag else "Episódio"
        nome_tag   = data_div.find('span', class_='serie') if data_div else None
        nome_anime = nome_tag.get_text(strip=True) if nome_tag else "Novo Anime"
        qual_tag   = artigo.find('span', class_='quality')
        qualidade  = qual_tag.get_text(strip=True) if qual_tag else "Desconhecida"
        spans      = data_div.find_all('span') if data_div else []
        data       = spans[0].get_text(strip=True) if spans else "Data não disponível"
        poster_div = artigo.find('div', class_='poster')
        img_tag    = poster_div.find('img') if poster_div else None
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

# ────────── Verificação e envio ──────────
async def verificar_episodios(conn, canal):
    episodios = get_ultimos_episodios()
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

            try:
                await canal.send(
                    content=f"<@&{ROLE_ID}>",
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(roles=True),
                    suppress_embeds=False
                )
                print(f"[DISCORD] ✅ Enviado: {ep['titulo_ep']}")
            except Exception as e:
                print(f"[DISCORD] ❌ Falha ao enviar: {e}")
        else:
            print(f"[BOT] Episódio já postado ou inválido: {ep['titulo_ep']}")

# ────────── Loop automático ──────────
async def checar_novos_episodios():
    await bot.wait_until_ready()
    canal = bot.get_channel(CANAL_ID)
    conn  = await conectar_banco()

    while not bot.is_closed():
        print("[⏱️] Verificação automática iniciada...")
        try:
            await verificar_episodios(conn, canal)
        except Exception as e:
            print(f"[ERRO] no loop automático: {e}")
        await asyncio.sleep(300)  # 5 minutos

# ────────── Comando !verificar ──────────
@bot.command()
@commands.has_permissions(administrator=True)
async def verificar(ctx):
    canal = ctx.channel
    conn = await conectar_banco()
    await ctx.send("🔍 Verificando episódios agora...")
    await verificar_episodios(conn, canal)

# ────────── Comando !limpar ──────────
@bot.command()
@commands.has_permissions(administrator=True)
async def limpar(ctx, link: str):
    conn = await conectar_banco()
    result = await conn.execute("DELETE FROM episodios_postados WHERE link = $1", link)

    if result == "DELETE 1":
        await ctx.send(f"🧹 Episódio removido do banco: {link}")
        print(f"[DB] ❌ Removido: {link}")
    else:
        await ctx.send("⚠️ Esse link não está registrado no banco.")
        print(f"[DB] Nenhum link removido: {link}")

# ────────── Evento on_ready ──────────
@bot.event
async def on_ready():
    print(f"[BOT] Online como {bot.user}")
    bot.loop.create_task(checar_novos_episodios())

# ────────── Keep-alive para Railway ──────────
app = Flask('')

@app.route('/')
def home():
    return "Bot ativo!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()
bot.run(TOKEN)
