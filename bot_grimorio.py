import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from flask import Flask
from threading import Thread

# === Mantém o bot online no Render ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Grimório ativo!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# === Configuração dos intents ===
intents = discord.Intents.default()
intents.message_content = False  # Slash commands não precisam disso
bot = commands.Bot(command_prefix="!", intents=intents)

# === Carrega o JSON de magias ===
def carregar_magias():
    caminho = "grimorio_completo.json"
    print(f"Tentando carregar magias de: {os.path.abspath(caminho)}")

    if not os.path.exists(caminho):
        print("❌ Arquivo grimorio_completo.json não encontrado no diretório!")
        return []

    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    print(f"✅ {len(dados)} registros brutos encontrados.")

    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    magias = []
    # Pode vir como lista simples ou agrupada por elemento
    for item in dados:
        if "magias" in item:  # Estrutura agrupada
            for m in item["magias"]:
                magias.append(m)
        elif "nome" in item:  # Estrutura simples
            magias.append(item)
    return magias

MAGIAS = carregar_magias()
MAGIA_MAP = {m.get("nome", "").lower(): m for m in MAGIAS}

# === Função para buscar magia ===
def buscar_magia(nome):
    return MAGIA_MAP.get(nome.lower())

# === Comando principal ===
@bot.tree.command(name="magia", description="Mostra detalhes de uma magia do grimório.")
@app_commands.describe(nome="Nome da magia que deseja consultar")
@app_commands.autocomplete(nome=lambda i, c: autocomplete_magias(i, c))
async def comando_magia(interaction: discord.Interaction, nome: str):
    magia = buscar_magia(nome)
    if not magia:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    def limpar(texto):
        return str(texto).replace("<br>", "").strip() if texto else "N/A"

    embed = discord.Embed(
        title=f"✨ {magia.get('nome', 'Sem nome')}",
        color=discord.Color.purple()
    )
    embed.set_author(name="Grimorio", icon_url="https://i.imgur.com/G2Y8XKX.png")

    embed.add_field(name="📘 Elemento", value=limpar(magia.get("elemento", "Desconhecido")), inline=False)
    embed.add_field(name="🧾 Descrição", value=limpar(magia.get("descricao", "Sem descrição.")), inline=False)
    embed.add_field(name="🎯 Efeito", value=limpar(magia.get("efeito", "Sem efeito.")), inline=False)
    embed.add_field(name="💧 Custo", value=limpar(magia.get("custo", "N/A")), inline=True)
    embed.add_field(name="⏳ Cooldown", value=limpar(magia.get("cooldown", "N/A")), inline=True)
    embed.add_field(name="🕓 Duração", value=limpar(magia.get("duracao", "N/A")), inline=True)
    embed.add_field(name="⚠️ Limitações", value=limpar(magia.get("limitacoes", "Nenhuma.")), inline=False)

    await interaction.response.send_message(embed=embed)

# === Autocomplete com segurança ===
async def autocomplete_magias(interaction: discord.Interaction, current: str):
    try:
        nomes = [m.get("nome", "") for m in MAGIAS if m.get("nome")]
        filtradas = [n for n in nomes if current.lower() in n.lower()]
        return [app_commands.Choice(name=n, value=n) for n in filtradas[:25]]
    except Exception as e:
        print("Erro no autocomplete:", e)
        return []

# === Inicialização ===
@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user}")
    try:
        await bot.tree.sync()
        print("🌙 Comandos sincronizados com sucesso.")
    except Exception as e:
        print("Erro ao sincronizar comandos:", e)

# === Executa o bot ===
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("⚠️ Variável de ambiente DISCORD_TOKEN não encontrada!")
else:
    bot.run(TOKEN)

