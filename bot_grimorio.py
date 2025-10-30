import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from flask import Flask
import threading

# 🔹 Carrega o JSON com as magias
with open("grimorio_completo.json", "r", encoding="utf-8") as f:
    magias = json.load(f)

# 🔹 Configura intents completas
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 🔹 Cria o servidor Flask (mantém o Render ativo)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot do Grimório está ativo! 🔮"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# 🔹 Busca a magia no JSON (case-insensitive)
def buscar_magia(nome):
    for magia in magias:
        if magia["titulo"].lower() == nome.lower():
            return magia
    return None

# =====================================================
# 🪄 SLASH COMMAND /magia
# =====================================================
@bot.tree.command(name="magia", description="Consulta uma magia do grimório pelo nome")
@app_commands.describe(nome="Nome exato da magia que deseja buscar")
async def slash_magia(interaction: discord.Interaction, nome: str):
    magia = buscar_magia(nome)
    if not magia:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada no grimório.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"✨ {magia['titulo']}",
        description=magia.get("descricao", "Sem descrição."),
        color=discord.Color.purple()
    )
    embed.add_field(name="📘 Elemento", value=magia.get("elemento", "Desconhecido"), inline=False)
    embed.add_field(name="📜 Detalhes", value=magia.get("efeito", "Sem efeito."), inline=False)
    embed.add_field(name="💧 Custo", value=magia.get("custo", "N/A"), inline=True)
    embed.add_field(name="⏳ Cooldown", value=magia.get("cooldown", "N/A"), inline=True)
    embed.add_field(name="🕓 Duração", value=magia.get("duracao", "N/A"), inline=True)
    if "limitações" in magia:
        embed.add_field(name="⚠️ Limitações", value=magia["limitações"], inline=False)

    await interaction.response.send_message(embed=embed)

# =====================================================
# 🪄 COMANDO DE TEXTO: !magia nome_da_magia
# =====================================================
@bot.command(name="magia")
async def comando_magia(ctx, *, nome: str):
    magia = buscar_magia(nome)
    if not magia:
        await ctx.send(f"❌ Magia **{nome}** não encontrada no grimório.")
        return

    msg = (
        f"**✨ {magia['titulo']}**\n"
        f"**Elemento:** {magia.get('elemento', 'Desconhecido')}\n\n"
        f"**Descrição:** {magia.get('descricao', 'Sem descrição.')}\n\n"
        f"**Efeito:** {magia.get('efeito', 'Sem efeito.')}\n\n"
        f"**Custo:** {magia.get('custo', 'N/A')}\n"
        f"**Cooldown:** {magia.get('cooldown', 'N/A')}\n"
        f"**Duração:** {magia.get('duracao', 'N/A')}\n"
    )
    if "limitações" in magia:
        msg += f"\n**Limitações:** {magia['limitações']}"

    await ctx.send(msg)

# =====================================================
# 🧭 AJUDA
# =====================================================
@bot.command(name="ajuda")
async def ajuda(ctx):
    msg = (
        "🔮 **Comandos do Bot do Grimório**\n\n"
        "**/magia [nome]** → Busca magias com autocomplete.\n"
        "**!magia [nome]** → Busca magias pelo nome (modo texto).\n"
        "**!ajuda** → Mostra esta mensagem."
    )
    await ctx.send(msg)

# =====================================================
# 🚀 EVENTO ON_READY
# =====================================================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot do Grimório online como {bot.user}!")
    print("Slash commands sincronizados com sucesso.")

# =====================================================
# 🌐 EXECUÇÃO
# =====================================================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(os.environ["DISCORD_TOKEN"])
