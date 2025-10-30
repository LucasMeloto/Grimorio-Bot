import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from flask import Flask
import threading
import unicodedata
import re

# =====================================================
# 🔹 Funções de Normalização
# =====================================================

def limpar_texto(texto: str) -> str:
    """Remove <br> e normaliza o texto."""
    if not isinstance(texto, str):
        return ""
    texto = texto.replace("<br>", "\n")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

def normalize_text(s):
    """Remove acentos e coloca em minúsculas."""
    if not isinstance(s, str):
        s = str(s)
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))

# =====================================================
# 🔹 Carrega o JSON e normaliza
# =====================================================
magias = []
try:
    with open("grimorio_completo.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
            for lista in data.values():
                if isinstance(lista, list):
                    magias.extend(lista)
        elif isinstance(data, list):
            magias = data
except Exception as e:
    print(f"Erro ao carregar o JSON: {e}")

print(f"✅ Magias carregadas: {len(magias)}")
print(f"Exemplo de magia: {magias[0].get('titulo', magias[0].get('Título', 'Sem título'))}")

def buscar_magia(nome):
    nome_norm = normalize_text(nome)

    for magia in magias:
        # tenta obter título em várias formas possíveis
        titulo = (
            magia.get("titulo")
            or magia.get("Título")
            or magia.get("nome")
            or magia.get("Nome")
            or ""
        )

        titulo_norm = normalize_text(str(titulo))

        if nome_norm in titulo_norm or titulo_norm in nome_norm:
            return magia

    print(f"[DEBUG] Magia não encontrada: {nome}")
    return None

# =====================================================
# 🔹 Configuração do Bot
# =====================================================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# =====================================================
# 🌐 Flask (para manter vivo no Render)
# =====================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot do Grimório está online! 🔮"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# =====================================================
# 🔮 Autocomplete de Magias
# =====================================================
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.describe(nome="Digite o nome da magia")
async def slash_magia(interaction: discord.Interaction, nome: str):
    magia = buscar_magia(nome)
    if not magia:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    titulo = limpar_texto(magia.get("titulo", ""))
    descricao = limpar_texto(magia.get("descricao", "Sem descrição."))
    efeito = limpar_texto(magia.get("efeito", "Sem efeito."))
    custo = limpar_texto(magia.get("custo", "N/A"))
    cooldown = limpar_texto(magia.get("cooldown", "N/A"))
    duracao = limpar_texto(magia.get("duracao", "N/A"))
    limitacoes = limpar_texto(magia.get("limitações", "Nenhuma."))
    elemento = limpar_texto(magia.get("elemento", "Desconhecido"))

    embed = discord.Embed(title=f"✨ {titulo}", color=discord.Color.purple())
    embed.add_field(name="📘 Elemento", value=elemento, inline=False)
    embed.add_field(name="📜 Descrição", value=descricao, inline=False)
    embed.add_field(name="🎯 Efeito", value=efeito, inline=False)
    embed.add_field(name="💧 Custo", value=custo, inline=True)
    embed.add_field(name="⏳ Cooldown", value=cooldown, inline=True)
    embed.add_field(name="🕓 Duração", value=duracao, inline=True)
    embed.add_field(name="⚠️ Limitações", value=limitacoes, inline=False)

    await interaction.response.send_message(embed=embed)

@slash_magia.autocomplete("nome")
async def autocomplete_magia(interaction: discord.Interaction, current: str):
    nomes = [m["titulo"] for m in magias if "titulo" in m]
    sugestoes = [app_commands.Choice(name=n, value=n) for n in nomes if current.lower() in n.lower()]
    return sugestoes[:25]

# =====================================================
# 🔹 Comando texto (!magia)
# =====================================================
@bot.command(name="magia")
async def comando_magia(ctx, *, nome: str):
    magia = buscar_magia(nome)
    if not magia:
        await ctx.send(f"❌ Magia **{nome}** não encontrada.")
        return

    titulo = limpar_texto(magia.get("titulo", ""))
    descricao = limpar_texto(magia.get("descricao", "Sem descrição."))
    efeito = limpar_texto(magia.get("efeito", "Sem efeito."))
    custo = limpar_texto(magia.get("custo", "N/A"))
    cooldown = limpar_texto(magia.get("cooldown", "N/A"))
    duracao = limpar_texto(magia.get("duracao", "N/A"))
    limitacoes = limpar_texto(magia.get("limitações", "Nenhuma."))
    elemento = limpar_texto(magia.get("elemento", "Desconhecido"))

    msg = (
        f"**✨ {titulo}**\n"
        f"**Elemento:** {elemento}\n\n"
        f"**Descrição:** {descricao}\n\n"
        f"**Efeito:** {efeito}\n\n"
        f"**Custo:** {custo}\n"
        f"**Cooldown:** {cooldown}\n"
        f"**Duração:** {duracao}\n"
        f"**Limitações:** {limitacoes}"
    )
    await ctx.send(msg)

# =====================================================
# 🔹 Evento on_ready
# =====================================================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online como {bot.user} com {len(magias)} magias carregadas!")

# =====================================================
# 🚀 Executa o Bot
# =====================================================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(os.environ["DISCORD_TOKEN"])


