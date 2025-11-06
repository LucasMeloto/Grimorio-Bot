import discord
from discord.ext import commands
from discord import app_commands
import json
from flask import Flask
import threading

# ===========================
# Configuração básica do bot
# ===========================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
TREE = bot.tree

# ===========================
# Leitura do Grimório
# ===========================
with open("grimorio_completo.json", "r", encoding="utf-8") as file:
    MAGIAS = json.load(file)

# Mapeia nomes de magias (em minúsculas) para o conteúdo completo
MAGIA_MAP = {m["nome"].lower(): m for elemento in MAGIAS for m in elemento["magias"]}

# ===========================
# Funções auxiliares
# ===========================
def limpar_texto(texto):
    """Remove tags <br> e espaços extras."""
    return texto.replace("<br>", "").replace("\n\n", "\n").strip()

def obter_valor(magia, chave, padrao="N/A"):
    """Obtém valor da magia com segurança."""
    return limpar_texto(magia.get(chave, padrao))

# ===========================
# Slash command: /magia
# ===========================
@TREE.command(name="magia", description="Consulta uma magia do Grimório.")
@app_commands.describe(nome="Nome da magia que deseja consultar")
@app_commands.autocomplete(nome=lambda interaction, current: [
    app_commands.Choice(name=magia["nome"], value=magia["nome"])
    for magia in MAGIA_MAP.values()
    if current.lower() in magia["nome"].lower()
][:25])
async def magia(interaction: discord.Interaction, nome: str):
    nome = nome.lower()
    magia = MAGIA_MAP.get(nome)

    if not magia:
        embed = discord.Embed(
            title="❌ Magia não encontrada",
            description=f"Não encontrei nenhuma magia chamada **{nome.title()}**.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    elemento = magia.get("elemento", "Desconhecido").capitalize()
    descricao = obter_valor(magia, "descricao", "Sem descrição.")
    efeito = obter_valor(magia, "efeito", "Sem efeito.")
    custo = obter_valor(magia, "custo", "N/A")
    cooldown = obter_valor(magia, "cooldown", "N/A")
    duracao = obter_valor(magia, "duracao", "N/A")
    limitacoes = obter_valor(magia, "limitacoes", "Nenhuma.")
    categoria = obter_valor(magia, "categoria", "Geral")

    embed = discord.Embed(
        title=f"✨ {magia['nome']}",
        color=discord.Color.blue()
    )
    embed.add_field(name="**Elemento:**", value=elemento, inline=False)
    embed.add_field(name="**Categoria:**", value=categoria, inline=False)
    embed.add_field(name="**Descrição:**", value=descricao, inline=False)
    embed.add_field(name="**Efeito:**", value=efeito, inline=False)
    embed.add_field(name="**Custo:**", value=custo, inline=True)
    embed.add_field(name="**Cooldown:**", value=cooldown, inline=True)
    embed.add_field(name="**Duração:**", value=duracao, inline=True)
    embed.add_field(name="**Limitações:**", value=limitacoes, inline=False)
    embed.set_footer(text="📜 Grimório Yo Paris")

    await interaction.response.send_message(embed=embed)

# ===========================
# Rota Flask (Render)
# ===========================
app = Flask("GrimorioBot")

@app.route("/")
def home():
    return "O Grimório está vivo!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

# ===========================
# Inicialização
# ===========================
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    await TREE.sync()
    print("🌐 Comandos sincronizados com sucesso.")

keep_alive()

# 🔑 Substitua pelo seu token do Discord
bot.run("SEU_TOKEN_AQUI")
