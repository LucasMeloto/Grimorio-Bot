import json
import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask

# =========================
# Configuração básica Flask (mantém o Render acordado)
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Grimório ativo!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

# =========================
# Carregamento de magias
# =========================
MAGIAS = []
MAGIA_MAP = {}

try:
    with open("grimorio_completo.json", "r", encoding="utf-8") as f:
        MAGIAS = json.load(f)
        if isinstance(MAGIAS, dict) and "magias" in MAGIAS:
            MAGIAS = MAGIAS["magias"]
        print(f"✅ JSON carregado com sucesso: {len(MAGIAS)} magias disponíveis.")
        for m in MAGIAS:
            nome = m.get("nome", "").lower()
            if nome:
                MAGIA_MAP[nome] = m
except Exception as e:
    print(f"❌ Erro ao carregar o arquivo grimorio_completo.json: {e}")

# =========================
# Configuração do bot
# =========================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🪄 Grimório conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"📜 {len(synced)} comandos sincronizados com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

# =========================
# Funções auxiliares
# =========================
def buscar_magia(nome):
    """Busca uma magia pelo nome (case insensitive)."""
    if not nome:
        return None
    nome = nome.lower()
    return MAGIA_MAP.get(nome)

# =========================
# Comando /magia
# =========================
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.describe(nome="Nome da magia que deseja consultar.")
@app_commands.autocomplete(nome=lambda interaction, current: [
    app_commands.Choice(name=m["nome"], value=m["nome"])
    for m in MAGIAS if current.lower() in m["nome"].lower()
][:25])
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
# Execução do bot
# =========================
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("❌ ERRO: Nenhum token encontrado na variável DISCORD_TOKEN.")
else:
    print("🚀 Iniciando bot...")
    bot.run(TOKEN)
