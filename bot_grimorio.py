import discord
from discord.ext import commands
from discord import app_commands
import json
from flask import Flask
import threading
import os

# ===========================
# CONFIGURAÇÕES
# ===========================
TOKEN = os.getenv("DISCORD_TOKEN")  # Defina no Render
JSON_PATH = "grimorio_completo.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ===========================
# LEITURA DO GRIMÓRIO
# ===========================
with open(JSON_PATH, "r", encoding="utf-8") as file:
    dados = json.load(file)

MAGIAS = []

# Caso o JSON contenha listas de elementos ou objetos mistos
for item in dados:
    if isinstance(item, dict):
        # formato plano
        if "nome" in item:
            MAGIAS.append(item)
        # formato com "magias" dentro (ex: {"elemento": "Fogo", "magias": [...]})
        elif "magias" in item:
            for magia in item["magias"]:
                if "nome" in magia:
                    magia["elemento"] = item.get("elemento", "Desconhecido")
                    MAGIAS.append(magia)

# cria mapa para busca rápida
MAGIA_MAP = {m["nome"].lower(): m for m in MAGIAS if "nome" in m}

# ===========================
# FUNÇÕES DE SUPORTE
# ===========================
def limpar_texto(texto: str):
    if not isinstance(texto, str):
        return ""
    return texto.replace("<br>", "\n").replace("<br/>", "\n").strip()

def buscar_magia(nome):
    nome = nome.lower()
    return MAGIA_MAP.get(nome)

# ===========================
# COMANDO /MAGIA
# ===========================
class Grimorio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="magia", description="Mostra informações detalhadas sobre uma magia do grimório.")
    @app_commands.describe(nome="Nome da magia que você deseja consultar.")
    async def comando_magia(self, interaction: discord.Interaction, nome: str):
        magia = buscar_magia(nome)
        if not magia:
            await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🪄 {magia.get('nome', 'Magia desconhecida')}",
            description=limpar_texto(magia.get("descricao", "")),
            color=discord.Color.blurple()
        )

        # adiciona campos se existirem
        if magia.get("efeito"):
            embed.add_field(name="🎯 Efeito", value=limpar_texto(magia["efeito"]), inline=False)
        if magia.get("custo"):
            embed.add_field(name="💠 Custo", value=str(magia["custo"]), inline=True)
        if magia.get("cooldown"):
            embed.add_field(name="⏳ Cooldown", value=str(magia["cooldown"]), inline=True)
        if magia.get("duracao"):
            embed.add_field(name="⌛ Duração", value=str(magia["duracao"]), inline=True)
        if magia.get("limitacoes"):
            embed.add_field(name="⚠️ Limitações", value=limpar_texto(magia["limitacoes"]), inline=False)
        if magia.get("categoria") or magia.get("elemento"):
            embed.set_footer(text=f"Categoria: {magia.get('categoria', 'Desconhecida')} • Elemento: {magia.get('elemento', 'Desconhecido')}")

        await interaction.response.send_message(embed=embed)

    # autocomplete
    @comando_magia.autocomplete("nome")
    async def autocomplete_magia(self, interaction: discord.Interaction, current: str):
        nomes = [m["nome"] for m in MAGIAS if "nome" in m and current.lower() in m["nome"].lower()]
        return [app_commands.Choice(name=n, value=n) for n in nomes[:25]]

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot conectado como {bot.user}")

bot.tree.add_command(Grimorio(bot).comando_magia)

# ===========================
# FLASK KEEP ALIVE
# ===========================
app = Flask(__name__)

@app.route('/')
def home():
    return "🧙‍♂️ Grimório Online e Conectado!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask).start()

# ===========================
# EXECUTAR BOT
# ===========================
bot.run(TOKEN)
