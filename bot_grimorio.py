import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from flask import Flask

# ========== CONFIGURAÇÃO ==========
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== FLASK KEEP-ALIVE ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot Grimório ativo."

def keep_alive():
    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# ========== CARREGAR MAGIAS ==========
CAMINHO_JSON = "grimorio_completo.json"

if not os.path.exists(CAMINHO_JSON):
    print("❌ Arquivo de magias não encontrado!")
    MAGIAS = []
else:
    with open(CAMINHO_JSON, "r", encoding="utf-8") as f:
        MAGIAS = json.load(f)
    print(f"✅ JSON carregado: {len(MAGIAS)} magias disponíveis.")

# Cria mapa rápido de magias
MAGIA_MAP = {m.get("nome", "").lower(): m for m in MAGIAS if "nome" in m}

# ========== AUTOCOMPLETE ==========
async def buscar_sugestoes(interaction: discord.Interaction, current: str):
    """Retorna até 25 magias que contenham o texto digitado."""
    current = current.lower()
    sugestoes = []
    for nome in MAGIA_MAP.keys():
        if current in nome:
            sugestoes.append(app_commands.Choice(name=nome[:100], value=nome))
        if len(sugestoes) >= 25:
            break
    if not sugestoes:
        sugestoes.append(app_commands.Choice(name="Nenhuma magia encontrada", value=""))
    print(f"[🔍 Autocomplete] {len(sugestoes)} sugestões geradas para '{current}'.")
    return sugestoes

# ========== COMANDO /MAGIA ==========
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.describe(nome="Nome da magia que deseja consultar")
@app_commands.autocomplete(nome=buscar_sugestoes)
async def comando_magia(interaction: discord.Interaction, nome: str):
    nome = nome.lower().strip()
    magia = MAGIA_MAP.get(nome)

    if not magia:
        print(f"❌ Magia '{nome}' não encontrada.")
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"✨ {magia.get('nome', 'Sem nome')}",
        color=discord.Color.orange()
    )
    embed.add_field(name="**Elemento:**", value=magia.get("elemento", "Desconhecido"), inline=False)
    embed.add_field(name="**Descrição:**", value=magia.get("descricao", "Sem descrição."), inline=False)
    embed.add_field(name="**Efeito:**", value=magia.get("efeito", "Sem efeito."), inline=False)
    embed.add_field(name="**Custo:**", value=magia.get("custo", "N/A"), inline=True)
    embed.add_field(name="**Cooldown:**", value=magia.get("cooldown", "N/A"), inline=True)
    embed.add_field(name="**Duração:**", value=magia.get("duracao", "N/A"), inline=True)
    embed.add_field(name="**Limitações:**", value=magia.get("limitacoes", "Nenhuma."), inline=False)
    
    await interaction.response.send_message(embed=embed)
    print(f"✅ Magia '{magia.get('nome')}' enviada para {interaction.user.name}.")

# ========== EVENTOS ==========
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🚀 Iniciando Grimório... Logado como {bot.user}")

# ========== EXECUÇÃO ==========
keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
