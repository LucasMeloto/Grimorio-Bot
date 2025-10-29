import json
import discord
from discord import app_commands
from discord.ext import commands
import os
import sys, types
if sys.version_info >= (3, 13):
    sys.modules["audioop"] = types.ModuleType("audioop")

# =============================
# CONFIGURAÇÃO INICIAL
# =============================
# Substitua seu token se for rodar localmente,
# mas no Render você colocará ele em "Environment Variables" (DISCORD_TOKEN)

TOKEN = os.getenv("DISCORD_TOKEN", "SEU_TOKEN_AQUI")

# Carregar JSON do grimório
with open("grimorio_completo.json", "r", encoding="utf-8") as f:
    magias = json.load(f)

# Lista de nomes das magias (para o autocomplete)
nomes_magias = [m["title"] for m in magias if "title" in m]

# =============================
# CONFIGURAÇÃO DO BOT
# =============================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =============================
# FUNÇÃO DE FORMATAÇÃO
# =============================
def formatar_magia(magia):
    desc = magia.get("description", "").replace("<br>", "\n").replace("<p>", "").replace("</p>", "")
    elemento = magia.get("element", "❓")
    categorias = ", ".join(magia.get("categories", []))

    embed = discord.Embed(
        title=f"{magia['title']}",
        description=f"{desc}",
        color=discord.Color.from_str("#8A2BE2")  # Roxo arcano ✨
    )
    embed.add_field(name="Elemento", value=elemento, inline=True)
    embed.add_field(name="Categorias", value=categorias, inline=True)
    embed.set_footer(text="📜 Grimório Yo'Paris • Feitiços e Magias")

    return embed

# =============================
# COMANDO PRINCIPAL
# =============================
class Grimorio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="magia", description="Consulta uma magia do grimório")
    @app_commands.describe(nome="Nome da magia")
    async def magia(self, interaction: discord.Interaction, nome: str):
        magia = next((m for m in magias if m["title"].lower() == nome.lower()), None)
        if not magia:
            await interaction.response.send_message("❌ Magia não encontrada no grimório.")
            return

        embed = formatar_magia(magia)
        await interaction.response.send_message(embed=embed)

    # 🔮 Auto-complete
    @magia.autocomplete("nome")
    async def magia_autocomplete(self, interaction: discord.Interaction, current: str):
        sugestões = [n for n in nomes_magias if current.lower() in n.lower()]
        return [app_commands.Choice(name=s, value=s) for s in sugestões[:25]]

async def setup(bot):
    await bot.add_cog(Grimorio(bot))

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔁 {len(synced)} comandos slash sincronizados.")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")

# =============================
# EXECUTAR BOT
# =============================
if __name__ == "__main__":
    bot.run(TOKEN)

