import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import re
from flask import Flask
import threading

# ==== CONFIGURAÇÃO FLASK PARA MANTER ONLINE ====
app = Flask(__name__)

@app.route('/')
def home():
    return "🪄 Grimório ativo!"

def run():
    app.run(host="0.0.0.0", port=8080)

# ==== FUNÇÕES DE SUPORTE ====
def normalizar(texto):
    return re.sub(r'[^a-zA-Z0-9]', '', texto.lower())

def carregar_magias():
    try:
        with open("grimorio_completo.json", "r", encoding="utf-8") as f:
            magias = json.load(f)
            print(f"✅ JSON carregado: {len(magias)} magias disponíveis.")
            return magias
    except Exception as e:
        print(f"❌ Erro ao carregar JSON: {e}")
        return []

magias = carregar_magias()

# ==== EMOJIS POR ELEMENTO ====
EMOJIS_ELEMENTOS = {
    "fire": "🔥",
    "water": "💧",
    "earth": "🌱",
    "air": "🌪️",
    "light": "🌟",
    "darkness": "🌑",
    "arcane": "🔮",
    "dimensional": "🌀",
    "status": "✨",
    "time": "⏳",
    "none": "⚪",
    "unknown": "❔"
}

# ==== FUNÇÕES PRINCIPAIS ====
def buscar_magia(nome):
    nome_normalizado = normalizar(nome)
    for magia in magias:
        if normalizar(magia.get("title", "")) == nome_normalizado:
            return magia
    return None

async def autocomplete_magias(interaction: discord.Interaction, current: str):
    lista = []
    for m in magias:
        titulo = m.get("title", "Sem título")
        if normalizar(current) in normalizar(titulo):
            lista.append(app_commands.Choice(name=titulo[:100], value=titulo))
        if len(lista) >= 25:
            break
    return lista

# ==== DISCORD BOT CONFIG ====
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ==== COMANDO /MAGIA ====
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.describe(nome="Nome da magia que deseja consultar")
@app_commands.autocomplete(nome=autocomplete_magias)
async def magia(interaction: discord.Interaction, nome: str):
    magia_info = buscar_magia(nome)
    if not magia_info:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    # Dados da magia
    titulo = magia_info.get("title", "Sem nome")
    descricao = magia_info.get("description", "Sem descrição.")
    elemento = magia_info.get("element", "unknown").capitalize()
    categorias = ", ".join(magia_info.get("categories", [])) or "Nenhuma"
    emoji_elemento = EMOJIS_ELEMENTOS.get(magia_info.get("element", "unknown").lower(), "❔")

    # Extrações opcionais
    efeito = magia_info.get("effect", "Sem efeito.")
    custo = magia_info.get("cost", "N/A")
    cooldown = magia_info.get("cooldown", "N/A")
    duracao = magia_info.get("duration", "N/A")
    limitacoes = magia_info.get("limitations", [])
    if isinstance(limitacoes, list):
        limitacoes_texto = "\n".join(limitacoes) if limitacoes else "Nenhuma."
    else:
        limitacoes_texto = limitacoes or "Nenhuma."

    # Detecção de GIF
    gif_match = re.search(r'<img.*?src="(.*?)"', descricao)
    gif_url = gif_match.group(1) if gif_match else None

    # Limpar HTML
    descricao_limpa = re.sub(r'<.*?>', '', descricao)

    embed = discord.Embed(
        title=f"{emoji_elemento} {titulo}",
        color=discord.Color.orange()
    )

    embed.add_field(name="🌈 Elemento:", value=f"{emoji_elemento} {elemento}", inline=False)
    embed.add_field(name="📜 Descrição:", value=descricao_limpa[:1024], inline=False)
    embed.add_field(name="🎯 Efeito:", value=str(efeito)[:1024], inline=False)
    embed.add_field(name="💧 Custo:", value=str(custo), inline=True)
    embed.add_field(name="⏳ Cooldown:", value=str(cooldown), inline=True)
    embed.add_field(name="⌛ Duração:", value=str(duracao), inline=True)
    embed.add_field(name="⚠️ Limitações:", value=limitacoes_texto[:1024], inline=False)
    embed.set_footer(text=f"Categorias: {categorias}")

    if gif_url:
        embed.set_image(url=gif_url)

    await interaction.response.send_message(embed=embed)

# ==== COMANDO /LISTAR ====
@bot.tree.command(name="listar", description="Lista magias por elemento ou nível.")
@app_commands.describe(filtro="Filtrar por elemento ou nível (básica, intermediária, avançada)")
async def listar(interaction: discord.Interaction, filtro: str = None):
    filtro = (filtro or "").lower()
    resultado = []

    for magia in magias:
        elemento = magia.get("element", "").lower()
        categorias = [c.lower() for c in magia.get("categories", [])]

        if filtro in elemento or filtro in categorias or filtro == "":
            resultado.append(f"• **{magia.get('title', 'Sem nome')}** ({elemento.capitalize()})")

    if not resultado:
        await interaction.response.send_message(f"❌ Nenhuma magia encontrada para o filtro **{filtro}**.", ephemeral=True)
        return

    mensagem = "\n".join(resultado)
    partes = [mensagem[i:i+1900] for i in range(0, len(mensagem), 1900)]

    for parte in partes:
        embed = discord.Embed(
            title=f"📜 Magias encontradas ({len(resultado)})",
            description=parte,
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed) if interaction.response.is_done() else await interaction.response.send_message(embed=embed)

# ==== EVENTOS ====
@bot.event
async def on_ready():
    print(f"🚀 Grimório iniciado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"📚 {len(synced)} comandos sincronizados com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

# ==== EXECUÇÃO ====
if __name__ == "__main__":
    threading.Thread(target=run).start()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Token do Discord não encontrado! Configure DISCORD_TOKEN nas variáveis de ambiente.")
    else:
        bot.run(TOKEN)
