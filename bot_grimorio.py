import discord
from discord.ext import commands
from discord import app_commands
import json
from flask import Flask
import threading
import os

# ===========================
# CONFIGURAÇÕES BÁSICAS
# ===========================
TOKEN = os.getenv("DISCORD_TOKEN")  # Defina seu token no Render
JSON_PATH = "grimorio_completo.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ===========================
# LEITURA DO GRIMÓRIO
# ===========================
with open(JSON_PATH, "r", encoding="utf-8") as file:
    MAGIAS = json.load(file)

# cria um dicionário para busca rápida
MAGIA_MAP = {m["nome"].lower(): m for m in MAGIAS}

# ===========================
# FUNÇÕES DE SUPORTE
# ===========================
def limpar_texto(texto: str):
    """Remove tags HTML e substitui <br> por quebras de linha reais."""
    if not isinstance(texto, str):
        return ""
    return texto.replace("<br>", "\n").replace("<br/>", "\n").strip()

def buscar_magia(nome):
    """Busca magia pelo nome (case-insensitive)."""
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

        # cria embed bonito
        embed = discord.Embed(
            title=f"🪄 {magia.get('nome', 'Magia desconhecida')}",
            description=limpar_texto(magia.get("descricao", "")),
            color=discord.Color.blurple()
        )

        # adiciona campos se existirem
        if "efeito" in magia:
            embed.add_field(name="🎯 Efeito", value=limpar_texto(magia["efeito"]), inline=False)
        if "custo" in magia:
            embed.add_field(name="💠 Custo", value=magia["custo"], inline=True)
        if "cooldown" in magia:
            embed.add_field(name="⏳ Cooldown", value=magia["cooldown"], inline=True)
        if "duracao" in magia:
            embed.add_field(name="⌛ Duração", value=magia["duracao"], inline=True)
        if "limitacoes" in magia:
            embed.add_field(name="⚠️ Limitações", value=limpar_texto(magia["limitacoes"]), inline=False)
        if "categoria" in magia:
            embed.set_footer(text=f"Categoria: {magia['categoria']} • Elemento: {magia.get('elemento', 'Desconhecido')}")

        await interaction.response.send_message(embed=embed)

    # ===========================
    # AUTOCOMPLETE
    # ===========================
    @comando_magia.autocomplete("nome")
    async def autocomplete_magia(self, interaction: discord.Interaction, current: str):
        nomes = [m["nome"] for m in MAGIAS if current.lower() in m["nome"].lower()]
        return [app_commands.Choice(name=n, value=n) for n in nomes[:25]]

# adiciona o comando ao bot
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
# INICIAR BOT
# ===========================
bot.run(TOKEN)
