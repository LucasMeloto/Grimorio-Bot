import json
import discord
from discord import app_commands
from discord.ext import commands
import os
import threading
from flask import Flask

# =========================
# Flask (mantém o Render ativo)
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Grimório ativo e desperto!"

def iniciar_flask():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=iniciar_flask).start()

# =========================
# Carregar magias do JSON
# =========================
MAGIAS = []
MAGIA_MAP = {}

try:
    with open("grimorio_completo.json", "r", encoding="utf-8") as f:
        MAGIAS = json.load(f)
        if isinstance(MAGIAS, dict) and "magias" in MAGIAS:
            MAGIAS = MAGIAS["magias"]
        print(f"✅ JSON carregado: {len(MAGIAS)} magias disponíveis.")
        for m in MAGIAS:
            nome = m.get("nome", "").lower()
            if nome:
                MAGIA_MAP[nome] = m
except Exception as e:
    print(f"❌ Erro ao carregar grimorio_completo.json: {e}")

# =========================
# Configuração do Bot
# =========================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🪄 Grimório conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"📜 {len(synced)} comandos sincronizados.")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

# =========================
# Funções auxiliares
# =========================
def buscar_magia(nome):
    if not nome:
        return None
    return MAGIA_MAP.get(nome.lower())

# =========================
# Autocomplete da barra /
# =========================
async def autocomplete_magia(interaction: discord.Interaction, current: str):
    choices = []
    for magia in MAGIAS:
        nome = magia.get("nome", "")
        if current.lower() in nome.lower():
            choices.append(app_commands.Choice(name=nome, value=nome))
        if len(choices) >= 25:
            break
    return choices

# =========================
# Comando /magia
# =========================
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.describe(nome="Nome da magia que deseja consultar.")
@app_commands.autocomplete(nome=autocomplete_magia)
async def comando_magia(interaction: discord.Interaction, nome: str):
    magia = buscar_magia(nome)
    if not magia:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"✨ {magia.get('nome', 'Magia desconhecida')}",
        color=discord.Color.purple()
    )
    embed.add_field(name="🧬 Elemento", value=magia.get("elemento", "Desconhecido"), inline=False)
    embed.add_field(name="📜 Descrição", value=magia.get("descricao", "Sem descrição."), inline=False)
    embed.add_field(name="🎯 Efeito", value=magia.get("efeito", "Sem efeito."), inline=False)
    embed.add_field(name="💧 Custo", value=magia.get("custo", "N/A"), inline=True)
    embed.add_field(name="⏳ Cooldown", value=magia.get("cooldown", "N/A"), inline=True)
    embed.add_field(name="🕓 Duração", value=magia.get("duracao", "N/A"), inline=True)
    embed.add_field(name="⚠️ Limitações", value=magia.get("limitacoes", "Nenhuma."), inline=False)

    await interaction.response.send_message(embed=embed)

# =========================
# Rodar bot
# =========================
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("❌ ERRO: Nenhum token encontrado na variável DISCORD_TOKEN.")
else:
    print("🚀 Iniciando Grimório...")
    bot.run(TOKEN)
