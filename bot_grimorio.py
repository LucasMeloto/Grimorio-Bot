import discord
from discord import app_commands
from discord.ext import commands
import json
import re
import os
from flask import Flask
import threading

# === CONFIGURAÇÃO DO BOT ===
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN = os.getenv("DISCORD_TOKEN")

# === CARREGAR O JSON ===
ARQUIVO_JSON = "grimorio_completo.json"
with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
    magias = json.load(f)

print(f"✅ JSON carregado: {len(magias)} magias disponíveis.")

# === FUNÇÕES AUXILIARES ===
def normalizar(texto):
    return re.sub(r"[^a-z0-9]", "", texto.lower())

def limpar_html(texto):
    """Remove tags HTML e converte quebras de linha em espaços."""
    texto = re.sub(r"<img[^>]*>", "", texto)
    texto = texto.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    texto = re.sub(r"\n{3,}", "\n\n", texto)  # Limita múltiplas quebras
    return texto.strip()

def buscar_magia(nome):
    nome_normalizado = normalizar(nome)
    for magia in magias:
        if normalizar(magia["title"]) == nome_normalizado:
            return magia
    return None

def get_element_emoji(element):
    emojis = {
        "fire": "🔥", "water": "💧", "earth": "⛰️", "air": "🌪️",
        "light": "✨", "dark": "🌑", "arcano": "🔮", "dimensional": "🌀",
        "time": "⌛", "ice": "❄️", "lightning": "⚡", "status": "🧬"
    }
    return emojis.get(element.lower(), "📘")

# === AUTOCOMPLETE ===
async def autocomplete_magias(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=m["title"], value=m["title"])
        for m in magias
        if current.lower() in m["title"].lower()
    ][:25]

# === COMANDO /magia ===
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.autocomplete(nome=autocomplete_magias)
async def magia(interaction: discord.Interaction, nome: str):
    magia_info = buscar_magia(nome)

    if not magia_info:
        await interaction.response.send_message("❌ Magia não encontrada.", ephemeral=True)
        return

    titulo = magia_info.get("title", "Sem título")
    elemento = magia_info.get("element", "Desconhecido").capitalize()
    emoji = get_element_emoji(elemento)

    descricao = limpar_html(magia_info.get("description", "Sem descrição."))
    categorias = ", ".join(magia_info.get("categories", [])) or "Nenhuma."

    # === EXTRAIR GIF ===
    gif_match = re.search(r'<img[^>]+src="([^"]+)"', magia_info.get("description", ""))
    gif_url = gif_match.group(1) if gif_match else None

    # === EXTRAIR CAMPOS ===
    def extrair_bloco(texto, chave):
        padrao = rf"{chave}:(.*?)(?=\n\S|$)"
        match = re.search(padrao, texto, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else "N/A"

    custo = extrair_bloco(descricao, "Custo")
    cooldown = extrair_bloco(descricao, "Cooldown")
    duracao = extrair_bloco(descricao, "Duração")
    efeito = extrair_bloco(descricao, "Efeito")
    limitacoes = extrair_bloco(descricao, "Limitações")

    # === EMBED ===
    embed = discord.Embed(
        title=f"{emoji} {titulo}",
        color=discord.Color.orange()
    )
    embed.add_field(name="🧭 Elemento:", value=elemento, inline=False)
    embed.add_field(name="📜 Descrição:", value=descricao, inline=False)
    embed.add_field(name="🎯 Efeito:", value=efeito or "Sem efeito.", inline=False)
    embed.add_field(name="💧 Custo:", value=custo, inline=True)
    embed.add_field(name="⏳ Cooldown:", value=cooldown, inline=True)
    embed.add_field(name="⌛ Duração:", value=duracao, inline=True)
    embed.add_field(name="⚠️ Limitações:", value=limitacoes or "Nenhuma.", inline=False)
    embed.set_footer(text=f"Categorias: {categorias}")

    if gif_url:
        embed.set_image(url=gif_url)

    await interaction.response.send_message(embed=embed)

# === COMANDO /listar ===
@bot.tree.command(name="listar", description="Lista as magias por elemento e tipo.")
async def listar(interaction: discord.Interaction):
    elementos = {}
    for m in magias:
        elem = m.get("element", "Desconhecido").capitalize()
        categorias = m.get("categories", [])
        nivel = next((c for c in categorias if c.lower() in ["basico", "intermediario", "avançado", "supremo"]), "Comum")
        if elem not in elementos:
            elementos[elem] = {}
        if nivel not in elementos[elem]:
            elementos[elem][nivel] = []
        elementos[elem][nivel].append(m["title"])

    texto = ""
    for elem, niveis in elementos.items():
        texto += f"**{get_element_emoji(elem)} {elem}**\n"
        for nivel, lista in niveis.items():
            texto += f"  🔹 **{nivel}:** {', '.join(lista)}\n"
        texto += "\n"

    await interaction.response.send_message(embed=discord.Embed(
        title="📚 Magias por Elemento",
        description=texto,
        color=discord.Color.blue()
    ))

# === FLASK (mantém o bot ativo no Render) ===
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Grimório Online!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def iniciar_flask():
    threading.Thread(target=run_flask).start()

# === INICIAR BOT ===
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🤖 Logado como {bot.user}")

iniciar_flask()
bot.run(TOKEN)
