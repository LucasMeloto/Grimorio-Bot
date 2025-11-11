import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
import asyncio

# ========= CONFIGURAÇÃO DO FLASK =========
app = Flask(__name__)

@app.route('/')
def home():
    return "Grimório ativo!"

@app.route('/ping')
def ping():
    return "pong"

# ========= CONFIGURAÇÃO DO DISCORD =========
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========= CARREGAR O JSON =========
with open("grimorio_completo.json", "r", encoding="utf-8") as f:
    MAGIAS = json.load(f)

print(f"✅ JSON carregado: {len(MAGIAS)} magias disponíveis.")

# ========= MAPEAR ELEMENTOS PARA EMOJIS =========
ELEMENTOS_EMOJIS = {
    "fire": "🔥",
    "water": "💧",
    "earth": "🌱",
    "air": "🌪️",
    "light": "☀️",
    "dark": "💀",
    "ice": "❄️",
    "lightning": "⚡",
    "arcane": "🔮",
    "dimensional": "🌌",
    "time": "⏳",
    "status": "✨"
}

# ========= FUNÇÃO PARA LIMITAR TEXTO =========
def limitar_texto(texto, limite=1024):
    if not texto:
        return "N/A"
    return texto if len(texto) <= limite else texto[:limite - 3] + "..."

# ========= FUNÇÃO PARA BUSCAR MAGIA =========
def buscar_magia(nome):
    for magia in MAGIAS:
        if magia["title"].lower() == nome.lower():
            return magia
    return None

# ========= FUNÇÃO ASSÍNCRONA DE AUTOCOMPLETE =========
async def autocomplete_magia(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=m["title"], value=m["title"])
        for m in MAGIAS if current.lower() in m["title"].lower()
    ][:25]

# ========= COMANDO /MAGIA =========
@app_commands.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.autocomplete(nome=autocomplete_magia)
async def comando_magia(interaction: discord.Interaction, nome: str):
    magia = buscar_magia(nome)

    if not magia:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    elemento = magia.get("element", "Desconhecido")
    emoji = ELEMENTOS_EMOJIS.get(elemento.lower(), "✨")
    elemento_formatado = f"{emoji} {elemento.capitalize()}"

    descricao = magia.get("description", "Sem descrição.")
    efeito = magia.get("effect", "Sem efeito.")
    custo = magia.get("cost", "N/A")
    cooldown = magia.get("cooldown", "N/A")
    duracao = magia.get("duration", "N/A")
    limitacoes = magia.get("limitations", [])
    categorias = magia.get("categories", [])
    gif_url = magia.get("gif", None)

    # Limitar texto
    descricao = limitar_texto(descricao)
    efeito = limitar_texto(efeito)
    custo = limitar_texto(str(custo))
    cooldown = limitar_texto(str(cooldown))
    duracao = limitar_texto(str(duracao))
    limitacoes_texto = limitar_texto("\n".join(limitacoes) if isinstance(limitacoes, list) else str(limitacoes))
    categorias_texto = ", ".join(categorias) if categorias else "Nenhuma."

    embed = discord.Embed(
        title=f"✨ {magia['title']}",
        color=discord.Color.orange()
    )
    embed.add_field(name="🧩 Elemento", value=elemento_formatado, inline=False)
    embed.add_field(name="📜 Descrição", value=descricao, inline=False)
    embed.add_field(name="🎯 Efeito", value=efeito, inline=False)
    embed.add_field(name="💧 Custo", value=custo, inline=True)
    embed.add_field(name="⏳ Cooldown", value=cooldown, inline=True)
    embed.add_field(name="🕒 Duração", value=duracao, inline=True)
    embed.add_field(name="⚠️ Limitações", value=limitacoes_texto, inline=False)
    embed.add_field(name="📚 Categorias", value=categorias_texto, inline=False)

    if gif_url:
        embed.set_image(url=gif_url)

    await interaction.response.send_message(embed=embed)

# ========= REGISTRO DO COMANDO =========
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🚀 Bot conectado como {bot.user}")

# ========= EXECUTAR O BOT =========
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ ERRO: Token do bot não encontrado. Verifique a variável DISCORD_TOKEN no Render.")
    else:
        async def start_bot():
            async with bot:
                await bot.start(TOKEN)

        import threading
        threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8080), daemon=True).start()

        import asyncio
        asyncio.run(start_bot())

