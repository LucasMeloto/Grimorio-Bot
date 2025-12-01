import discord
from discord import app_commands
from discord.ext import commands
import json
import re
import os
from flask import Flask
import threading

# ============================
# FLASK — manter o bot online
# ============================

app = Flask(__name__)

@app.route("/")
def home():
    return "🪄 Grimório ativo!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ============================
# FUNÇÕES AUXILIARES
# ============================

def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def limpar_html(texto: str) -> str:
    if not texto:
        return ""

    # pegar imagem (apenas a primeira)
    img_match = re.search(r'<img[^>]*src="([^"]+)"', texto, flags=re.IGNORECASE)
    gif_url = img_match.group(1) if img_match else None

    # remover imagens
    texto = re.sub(r"<img[^>]*>", "", texto, flags=re.IGNORECASE)

    # converter quebras de linha básicas
    texto = re.sub(r"</?(p|div|span|strong|em|b|i|u|br)[^>]*>", "\n", texto, flags=re.IGNORECASE)

    # reduzir quebras
    texto = re.sub(r"\n{2,}", "\n\n", texto)

    return texto.strip(), gif_url


def extrair_campos(desc: str):
    texto_limpo, gif_url = limpar_html(desc)

    def busca(pattern):
        m = re.search(pattern, texto_limpo, flags=re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else None

    efeito = busca(r"(?:^|\n)Efeito\s*:\s*(.+?)(?:\n|$)")
    custo = busca(r"(?:^|\n)Custo\s*:\s*(.+?)(?:\n|$)")
    cooldown = busca(r"(?:^|\n)Cooldown\s*:\s*(.+?)(?:\n|$)")
    duracao = busca(r"(?:^|\n)Dura(?:ç|c)[aã]o\s*:\s*(.+?)(?:\n|$)")
    limitacoes_raw = busca(r"(?:^|\n)Limita(?:ç|c)[oõ]es\s*:\s*(.+?)(?:$|\n)")

    # descrição antes do "Efeito:"
    desc_base = re.split(r"(^|\n)Efeito\s*:", texto_limpo, flags=re.IGNORECASE)[0].strip()

    # lista de limitações
    lista_lim = []
    if limitacoes_raw:
        for line in re.split(r"\.|\n", limitacoes_raw):
            line = line.strip()
            if line:
                lista_lim.append(line)

    return desc_base, efeito, custo, cooldown, duracao, lista_lim, gif_url


# ============================
# CARREGAR JSON
# ============================

ARQUIVO_JSON = "grimorio_completo.json"

try:
    with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
        dados = json.load(f)
except Exception as e:
    print(f"❌ Erro ao carregar JSON: {e}")
    dados = []

MAGIAS = []

# aceitando arquivos agrupados por elemento OU simples
if isinstance(dados, list) and dados and isinstance(dados[0], dict) and "magias" in dados[0]:
    for bloco in dados:
        elemento = bloco.get("element") or bloco.get("elemento")
        for m in bloco.get("magias", []):
            if "element" not in m and "elemento" not in m:
                m["element"] = elemento
            MAGIAS.append(m)
else:
    MAGIAS = dados

print(f"✅ Total de magias indexadas: {len(MAGIAS)}")

# ============================
# EMOJIS POR ELEMENTO
# ============================

EMOJI_ELEMENTOS = {
    "fire": "🔥", "fogo": "🔥",
    "water": "💧", "água": "💧", "agua": "💧",
    "earth": "🌱", "terra": "🌱",
    "air": "🌪️", "ar": "🌪️",
    "light": "✨", "luz": "✨",
    "dark": "🌑", "escuridão": "🌑", "escuro": "🌑",
    "arcano": "🔮",
    "dimensional": "🌀",
    "tempo": "⌛", "time": "⌛",
    "status": "💠",
    "unknown": "❔"
}

def emoji_elemento(raw):
    if not raw:
        return "❔"
    key = raw.lower().strip()
    return EMOJI_ELEMENTOS.get(key, EMOJI_ELEMENTOS.get(key.split()[0], "❔"))

# ============================
# BOT DISCORD
# ============================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ============================
# AUTOCOMPLETE
# ============================

async def autocomplete_magias(interaction: discord.Interaction, current: str):
    norm = normalizar_texto(current)
    choices = []

    for m in MAGIAS:
        titulo = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or ""
        if norm in normalizar_texto(titulo):
            choices.append(app_commands.Choice(name=titulo[:100], value=titulo))

        if len(choices) >= 25:
            break

    return choices

# ============================
# /magia
# ============================

@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.autocomplete(nome=autocomplete_magias)
async def cmd_magia(interaction: discord.Interaction, nome: str):

    magia = None
    alvo = normalizar_texto(nome)

    for m in MAGIAS:
        titulo = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or ""
        if normalizar_texto(titulo) == alvo:
            magia = m
            break

    if not magia:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    titulo = magia.get("title") or magia.get("titulo") or magia.get("name") or magia.get("nome") or "Sem nome"
    elemento_raw = magia.get("element") or magia.get("elemento")
    emoji = emoji_elemento(elemento_raw)
    elemento_cap = elemento_raw.capitalize() if elemento_raw else "Desconhecido"

    desc_raw = magia.get("description") or magia.get("descricao") or ""

    desc_clean, efeito, custo, cooldown, duracao, lista_lim, gif = extrair_campos(desc_raw)

    categorias = magia.get("categories") or magia.get("categorias") or []
    categorias_text = ", ".join(categorias) if categorias else "Nenhuma"

    def truncar(t, lim=1024):
        return t[:lim-3] + "..." if len(t) > lim else t

    desc_clean = truncar(desc_clean)
    efeito = truncar(efeito or "Sem efeito.")
    limitacoes = "\n".join(f"- {l}" for l in lista_lim) if lista_lim else "Nenhuma."

    embed = discord.Embed(
        title=f"{emoji} {titulo}",
        color=discord.Color.orange()
    )

    embed.add_field(name="🔷 Elemento", value=f"{emoji} {elemento_cap}", inline=False)
    embed.add_field(name="📜 Descrição", value=desc_clean or "Sem descrição.", inline=False)
    embed.add_field(name="🎯 Efeito", value=efeito, inline=False)
    embed.add_field(name="💧 Custo", value=custo or "?", inline=True)
    embed.add_field(name="⏳ Cooldown", value=cooldown or "?", inline=True)
    embed.add_field(name="⌛ Duração", value=duracao or "?", inline=True)
    embed.add_field(name="⚠️ Limitações", value=truncar(limitacoes), inline=False)

    embed.set_footer(text=f"Categorias: {categorias_text}")

    if gif:
        embed.set_image(url=gif)

    await interaction.response.send_message(embed=embed)

# ============================
# /buscar
# ============================

@bot.tree.command(name="buscar", description="Busca magias pelo nome ou descrição.")
async def cmd_buscar(interaction: discord.Interaction, term: str):

    norm = normalizar_texto(term)
    encontrados = []

    for m in MAGIAS:
        titulo = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or ""
        desc = m.get("description") or m.get("descricao") or ""

        if norm in normalizar_texto(titulo) or norm in normalizar_texto(desc):
            encontrados.append(titulo)

        if len(encontrados) >= 25:
            break

    if not encontrados:
        await interaction.response.send_message(f"❌ Nenhuma magia encontrada para \"{term}\".", ephemeral=True)
        return

    texto = "\n".join(f"• {t}" for t in sorted(encontrados))
    texto = texto[:1024]

    embed = discord.Embed(
        title=f"🔍 Resultados ({len(encontrados)})",
        description=texto,
        color=discord.Color.blue()
    )

    await interaction.response.send_message(embed=embed)

# ============================
# EVENTO READY
# ============================

@bot.event
async def on_ready():
    print(f"🤖 Logado como {bot.user}")
    try:
        await bot.tree.sync()
        print("✅ Comandos sincronizados.")
    except Exception as e:
        print("❌ Erro ao sincronizar:", e)

# ============================
# INICIAR BOT
# ============================

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Defina DISCORD_TOKEN nas variáveis de ambiente.")
    else:
        bot.run(TOKEN)
