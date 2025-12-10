# ======================================
# BOT COMPLETO DO GRIMÓRIO (2025)
# Com correções de GIF + Buscar Inteligente + Listar
# ======================================

import discord
from discord import app_commands
from discord.ext import commands
import json
import re
import os
from flask import Flask
import threading

# ======================================
# KEEPALIVE FLASK
# ======================================
app = Flask(__name__)

@app.route("/")
def home():
    return "🪄 Grimório ativo!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ======================================
# FUNÇÕES UTILITÁRIAS
# ======================================

ELEMENT_ICONS = {
    "fogo": "🔥", "fire": "🔥",
    "água": "💧", "agua": "💧", "water": "💧",
    "terra": "🌱", "earth": "🌱",
    "ar": "🌬️", "vento": "🌬️", "wind": "🌬️",
    "raio": "⚡", "lightning": "⚡", "electric": "⚡",
    "luz": "☀️", "light": "☀️",
    "escuridão": "🌑", "escuro": "🌑", "dark": "🌑",
    "arcano": "🔮",
    "dimensional": "🌀",
    "tempo": "⌛",
    "status": "💠",
    "unknown": "❔"
}

ELEMENTOS_VALIDOS = [
    "fogo","fire","água","agua","water",
    "terra","earth","ar","vento","wind",
    "raio","lightning","electric",
    "luz","light","escuridão","dark",
    "arcano","dimensional","tempo","status"
]


def clean_string(text: str) -> str:
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r"^[^\wáéíóúãõâêôç]+", "", text)
    text = re.sub(r"[^\w\sáéíóúãõâêôç-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def get_element_icon(raw):
    clean = clean_string(raw)
    if clean in ELEMENT_ICONS:
        return clean, ELEMENT_ICONS[clean]

    first = clean.split()[0] if clean else ""
    if first in ELEMENT_ICONS:
        return clean, ELEMENT_ICONS[first]

    return clean, "❔"


def normalize_categories(raw):
    if not raw:
        return []
    out = []
    for c in raw:
        cl = clean_string(c)
        if cl:
            out.append(cl.capitalize())
    return out


def limpar_html_e_extrair_gif(texto: str):
    if not texto:
        return "", None

    s = str(texto)

    # Capturar GIF ANTES de limpar HTML
    gif = None

    # 1) <img src="">
    m = re.search(r'<img[^>]*src=[\'"]([^\'"]+\.(gif|mp4|webm))[\'"]', s, re.IGNORECASE)
    if m:
        gif = m.group(1)

    # 2) link direto .gif
    if not gif:
        m2 = re.search(r'(https?://[^\s\'"]+\.(gif|mp4|webm))', s, re.IGNORECASE)
        if m2:
            gif = m2.group(1)

    # Agora limpar HTML
    s = re.sub(r"<img[^>]*>", "", s)
    s = re.sub(r"</?(p|div|span|strong|em|b|i|u|br)[^>]*>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\r\n?", "\n", s)
    s = re.sub(r"\n{2,}", "\n\n", s)

    return s.strip(), gif


def extrair_campos_da_descricao(desc_raw):
    texto, gif = limpar_html_e_extrair_gif(desc_raw or "")
    if not texto:
        return "", "", "", "", "", [], gif

    def pegar(rotulos):
        for r in rotulos:
            pad = rf"(?:^|\n){r}\s*:\s*(.+?)(?:\n|$)"
            m = re.search(pad, texto, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    efeito = pegar(["Efeito"])
    custo = pegar(["Custo", "Mana"])
    cooldown = pegar(["Cooldown", "CD"])
    duracao = pegar(["Duração", "Duracao"])
    limitacoes_raw = pegar(["Limitações", "Limitacoes"])

    # Descrição base = antes de "Efeito:"
    parts = re.split(r"(?:^|\n)Efeito\s*:", texto, flags=re.IGNORECASE)
    desc_base = parts[0].strip() if parts else texto.strip()

    lista_lim = []
    if limitacoes_raw:
        for ln in re.split(r"[\.\n]", limitacoes_raw):
            ln = ln.strip()
            if ln:
                lista_lim.append(ln)

    return desc_base, efeito or "", custo or "", cooldown or "", duracao or "", lista_lim, gif


# ======================================
# CARREGAR JSON
# ======================================

ARQUIVO = "grimorio_completo.json"

try:
    with open(ARQUIVO, "r", encoding="utf-8") as f:
        dados = json.load(f)
except Exception as e:
    print("❌ Erro ao carregar JSON:", e)
    dados = []

MAGIAS = []


def normalize_spell_obj(m):
    title = m.get("title") or m.get("name") or "Sem título"

    raw_element = m.get("element") or m.get("elemento") or ""
    element_clean, icon = get_element_icon(raw_element)

    desc = m.get("description") or ""

    cats_raw = m.get("categories") or []
    cats = normalize_categories(cats_raw)

    return {
        "title": title,
        "element": element_clean,
        "icon": icon,
        "description": desc,
        "categories": cats,
        "_orig": m
    }


# JSON em blocos
if isinstance(dados, list) and dados and isinstance(dados[0], dict) and "magias" in dados[0]:
    for bloco in dados:
        elem = bloco.get("element") or ""
        for m in bloco["magias"]:
            if not m.get("element"):
                m["element"] = elem
            MAGIAS.append(normalize_spell_obj(m))
else:
    for m in dados:
        MAGIAS.append(normalize_spell_obj(m))

print(f"⚡ Magias carregadas: {len(MAGIAS)}")


# ======================================
# DISCORD BOT
# ======================================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# AUTOCOMPLETE
async def autocomplete_magias(inter, current):
    norm = clean_string(current)
    out = []
    for m in MAGIAS:
        if norm in clean_string(m["title"]):
            out.append(app_commands.Choice(name=m["title"][:100], value=m["title"]))
        if len(out) >= 25:
            break
    return out


# ======================================
# /MAGIA
# ======================================
@bot.tree.command(name="magia", description="Consulta detalhes de uma magia.")
@app_commands.autocomplete(nome=autocomplete_magias)
async def cmd_magia(interaction, nome: str):

    alvo = clean_string(nome)
    magia = None

    for m in MAGIAS:
        if clean_string(m["title"]) == alvo:
            magia = m
            break

    if not magia:
        return await interaction.response.send_message(
            f"❌ Magia **{nome}** não encontrada.", ephemeral=True
        )

    desc_raw = magia["description"]
    desc_clean, efeito, custo, cooldown, duracao, lista_lim, gif = extrair_campos_da_descricao(desc_raw)

    titulo = magia["title"]
    emoji = magia["icon"]
    elemento = magia["element"].capitalize()
    categorias = ", ".join(magia["categories"]) or "Nenhuma"

    def trunc(t, lim=1024):
        return t if len(t) <= lim else t[:lim-3] + "..."

    embed = discord.Embed(title=f"{emoji} {titulo}", color=discord.Color.orange())
    embed.add_field(name="🔷 Elemento", value=f"{emoji} {elemento}", inline=False)
    embed.add_field(name="📜 Descrição", value=trunc(desc_clean), inline=False)
    embed.add_field(name="🎯 Efeito", value=trunc(efeito), inline=False)
    embed.add_field(name="💧 Custo", value=custo or "?", inline=True)
    embed.add_field(name="⏳ Cooldown", value=cooldown or "?", inline=True)
    embed.add_field(name="⌛ Duração", value=duracao or "?", inline=True)
    embed.add_field(
        name="⚠️ Limitações",
        value="\n".join(f"- {l}" for l in lista_lim) or "Nenhuma.",
        inline=False
    )
    embed.set_footer(text=f"Categorias: {categorias}")

    if gif:
        embed.set_image(url=gif)

    await interaction.response.send_message(embed=embed)


# ======================================
# /BUSCAR – INTELIGENTE
# ======================================
@bot.tree.command(name="buscar", description="Busca magias por nome, elemento, categoria ou descrição.")
async def cmd_buscar(interaction, term: str):

    norm = clean_string(term)
    resultados = []

    # Se termo for ELEMENTO VÁLIDO, busca restrita
    if norm in ELEMENTOS_VALIDOS:
        for m in MAGIAS:
            if norm == m["element"]:
                resultados.append(m["title"])
                continue

            if norm in clean_string(" ".join(m["categories"])):
                resultados.append(m["title"])
                continue

            if norm in clean_string(m["title"]):
                resultados.append(m["title"])
                continue

    else:
        # Busca geral
        for m in MAGIAS:
            titulo = m["title"]
            desc = m["description"]
            cats = " ".join(m["categories"])

            if (
                norm in clean_string(titulo)
                or norm in clean_string(cats)
                or norm in clean_string(desc)
            ):
                resultados.append(titulo)

    if not resultados:
        return await interaction.response.send_message(
            f"❌ Nada encontrado para **{term}**.", ephemeral=True
        )

    texto = "\n".join(f"• {r}" for r in sorted(resultados))
    if len(texto) > 4000:
        texto = texto[:3990] + "\n... (lista truncada)"

    embed = discord.Embed(
        title=f"🔍 Resultados da busca ({len(resultados)})",
        description=texto,
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)


# ======================================
# /LISTAR
# ======================================
@bot.tree.command(name="listar", description="Lista magias por elemento, categoria ou todas.")
async def cmd_listar(interaction, filtro: str):

    norm = clean_string(filtro)
    resultados = []

    for m in MAGIAS:

        if norm == "todas":
            resultados.append(m["title"])
            continue

        # por elemento
        if norm == m["element"]:
            resultados.append(m["title"])
            continue

        # por categoria
        if norm in clean_string(" ".join(m["categories"])):
            resultados.append(m["title"])
            continue

    if not resultados:
        return await interaction.response.send_message(
            f"❌ Nada encontrado para **{filtro}**.", ephemeral=True
        )

    texto = "\n".join(f"• {r}" for r in sorted(resultados))
    if len(texto) > 4000:
        texto = texto[:3990] + "\n... (lista truncada)"

    embed = discord.Embed(
        title=f"📘 Lista ({len(resultados)}) — {filtro.capitalize()}",
        description=texto,
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


# ======================================
# READY
# ======================================
@bot.event
async def on_ready():
    print(f"🤖 Conectado como {bot.user}")
    try:
        await bot.tree.sync()
        print("✨ Comandos sincronizados.")
    except Exception as e:
        print("❌ Erro ao sincronizar:", e)


# ======================================
# START
# ======================================
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Configure DISCORD_TOKEN!")
    else:
        bot.run(TOKEN)
