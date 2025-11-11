import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from waitress import serve
import json
import os
import asyncio
import threading
import unicodedata

# ============================================================
# CONFIGURAÇÃO BÁSICA
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")
ARQUIVO_MAGIAS = "magias.json"

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Grimório do Discord está online."

@app.route("/ping")
def ping():
    return "pong"

# ============================================================
# FUNÇÃO PARA REMOVER ACENTOS E NORMALIZAR STRINGS
# ============================================================

def normalizar(texto: str):
    if not texto:
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower().strip())
        if unicodedata.category(c) != 'Mn'
    )

# ============================================================
# CARREGAR MAGIAS
# ============================================================

try:
    with open(ARQUIVO_MAGIAS, "r", encoding="utf-8") as f:
        magias = json.load(f)
    print(f"✅ JSON carregado: {len(magias)} magias disponíveis.")
except Exception as e:
    print(f"❌ Erro ao carregar JSON: {e}")
    magias = []

# ============================================================
# CONFIGURAÇÃO DO BOT
# ============================================================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

ELEMENTOS_EMOJIS = {
    "Fogo": "🔥",
    "Água": "💧",
    "Terra": "🌱",
    "Ar": "💨",
    "Raio": "⚡",
    "Gelo": "❄️",
    "Luz": "✨",
    "Escuridão": "🌑",
    "Tempo": "⏳",
    "Dimensional": "🌌",
    "Status": "💠",
    "Arcano": "🔮",
    "Sem Elemento": "⚙️"
}

# ============================================================
# FUNÇÕES DE APOIO
# ============================================================

def buscar_magia(nome_magia):
    nome_normalizado = normalizar(nome_magia)
    for magia in magias:
        if normalizar(magia["nome"]) == nome_normalizado:
            return magia
    return None

async def autocomplete_magias(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=m["nome"], value=m["nome"])
        for m in magias if normalizar(current) in normalizar(m["nome"])
    ][:25]

# ============================================================
# COMANDO /MAGIA
# ============================================================

@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.autocomplete(nome=autocomplete_magias)
async def magia(interaction: discord.Interaction, nome: str):
    magia_info = buscar_magia(nome)
    if not magia_info:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    elemento = magia_info.get("elemento", "Sem Elemento").capitalize()
    emoji_elemento = ELEMENTOS_EMOJIS.get(elemento, "📘")

    descricao = magia_info.get("descricao", "Sem descrição.")
    efeito = magia_info.get("efeito", "Sem efeito.")
    custo = magia_info.get("custo", "Não informado.")
    cooldown = magia_info.get("cooldown", "Não informado.")
    duracao = magia_info.get("duracao", "Não informado.")
    limitacoes = magia_info.get("limitacoes", [])
    gif = magia_info.get("gif", "")

    # Concatena todas as limitações
    if isinstance(limitacoes, list):
        limitacoes_texto = "\n".join(f"- {l}" for l in limitacoes)
    else:
        limitacoes_texto = str(limitacoes)

    embed = discord.Embed(
        title=f"{emoji_elemento} {magia_info['nome']}",
        description=f"**Elemento:** {elemento}\n\n{descricao}",
        color=discord.Color.purple()
    )
    embed.add_field(name="✨ Efeito", value=efeito, inline=False)
    embed.add_field(name="💰 Custo de Mana", value=custo, inline=True)
    embed.add_field(name="⏱️ Cooldown", value=cooldown, inline=True)
    embed.add_field(name="⌛ Duração", value=duracao, inline=True)
    embed.add_field(name="⚠️ Limitações", value=limitacoes_texto or "Nenhuma.", inline=False)

    if gif:
        embed.set_image(url=gif)

    await interaction.response.send_message(embed=embed)

# ============================================================
# COMANDO /LISTAR
# ============================================================

@bot.tree.command(name="listar", description="Lista todas as magias por elemento e nível.")
async def listar(interaction: discord.Interaction):
    elementos_organizados = {}

    # Organiza as magias por elemento e nível
    for m in magias:
        elem = m.get("elemento", "Sem Elemento").capitalize()
        nivel = m.get("nivel", "Básica").capitalize()
        elementos_organizados.setdefault(elem, {"Básica": [], "Intermediária": [], "Avançada": []})
        elementos_organizados[elem][nivel].append(m["nome"])

    embeds = []

    for elemento, niveis in elementos_organizados.items():
        emoji = ELEMENTOS_EMOJIS.get(elemento, "📘")
        embed = discord.Embed(
            title=f"{emoji} {elemento}",
            color=discord.Color.dark_purple()
        )
        for nivel, lista in niveis.items():
            if lista:
                embed.add_field(
                    name=f"🌀 {nivel}",
                    value="\n".join(sorted(lista)),
                    inline=False
                )
        embeds.append(embed)

    for embed in embeds:
        await interaction.channel.send(embed=embed)

    await interaction.response.send_message("📜 Magias listadas com sucesso!", ephemeral=True)

# ============================================================
# EVENTO ON_READY
# ============================================================

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos sincronizados.")
        print(f"🤖 Bot conectado como {bot.user}")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

# ============================================================
# EXECUÇÃO NO RENDER
# ============================================================

def iniciar_bot():
    asyncio.run(bot.start(TOKEN))

if __name__ == "__main__":
    threading.Thread(target=iniciar_bot).start()
    serve(app, host="0.0.0.0", port=8080)
