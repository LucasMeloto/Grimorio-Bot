# bot.py
import discord
from discord import app_commands
from discord.ext import commands
import json
import re
import os
from flask import Flask
import threading

# -------------------------
# KEEPALIVE (Flask)
# -------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "🪄 Grimório ativo!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# -------------------------
# UTILITÁRIOS: normalização
# -------------------------

# Mapeamento de elementos -> emoji
ELEMENT_ICONS = {
    "fogo": "🔥", "fire": "🔥",
    "água": "💧", "agua": "💧", "water": "💧",
    "terra": "🌱", "earth": "🌱",
    "ar": "🌬️", "vento": "🌬️", "wind": "🌬️",
    "raio": "⚡", "lightning": "⚡", "electric": "⚡",
    "luz": "☀️", "light": "☀️",
    "escuridão": "🌑", "escuro": "🌑", "dark": "🌑", "trevas": "🌑",
    "arcano": "🔮", "dimensional": "🌀", "tempo": "⌛", "status": "💠",
    "neutral": "❔", "neutro": "❔", "unknown": "❔"
}

def clean_string(text: str) -> str:
    """Remove emojis/ícones e caracteres estranhos, devolve lowercase limpo."""
    if not text:
        return ""
    text = str(text)
    # remove leading/trailing spaces
    text = text.strip()
    # remove emoji/glyphs at start (tudo que não seja letra/dígito/acento)
    text = re.sub(r"^[^\wáéíóúãõâêôç]+", "", text)
    # remove emojis/punctuation no meio (mantém letras, números e espaços)
    text = re.sub(r"[^\w\sáéíóúãõâêôç-]", "", text)
    # normalize spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()

def get_element_icon(raw_element: str) -> tuple[str, str]:
    """
    Retorna (element_clean, icon).
    Se não encontrar, devolve elemento limpo e fallback '❔'.
    """
    clean = clean_string(raw_element)
    icon = ELEMENT_ICONS.get(clean)
    if icon:
        return clean, icon
    # tentar segunda chance: pegar a primeira palavra
    first = clean.split()[0] if clean else ""
    icon = ELEMENT_ICONS.get(first)
    if icon:
        return clean, icon
    # fallback: se raw já contenha emoji no começo, tenta extrair emoji
    emoji_search = re.match(r"^([^\w\s])+", raw_element or "")
    if emoji_search:
        return clean, emoji_search.group(0)
    return clean, "❔"

def normalize_categories(raw_cats):
    if not raw_cats:
        return []
    out = []
    for c in raw_cats:
        cl = clean_string(c)
        if cl:
            out.append(cl.capitalize())
    return out

# -------------------------
# EXTRAÇÃO DE CAMPOS DA DESCRIPTION
# -------------------------
def limpar_html_e_extrair_gif(texto: str):
    """Retira tags HTML e captura a primeira URL de imagem (gif/mp4/webm) se houver."""
    if not texto:
        return "", None
    s = str(texto)
    # captura gif/mp4/webm/url de imagem via src ou link direto
    gif = None
    # tenta src em <img>
    m = re.search(r'<img[^>]*src=[\'"]([^\'"]+)[\'"]', s, flags=re.IGNORECASE)
    if m:
        gif = m.group(1)
    else:
        # tenta qualquer url que termine com gif/mp4/webm
        m2 = re.search(r'(https?://[^\s\'"]+\.(?:gif|mp4|webm))', s, flags=re.IGNORECASE)
        if m2:
            gif = m2.group(1)

    # remover tags de imagem e tags HTML comuns
    s = re.sub(r"<img[^>]*>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"</?(p|div|span|strong|em|b|i|u|br)[^>]*>", "\n", s, flags=re.IGNORECASE)
    # remover demais tags HTML
    s = re.sub(r"<[^>]+>", "", s)
    # normalizar quebras
    s = re.sub(r"\r\n?", "\n", s)
    s = re.sub(r"\n{2,}", "\n\n", s)
    return s.strip(), gif

def extrair_campos_da_descricao(desc_raw: str):
    """
    Retorna: desc_base, efeito, custo, cooldown, duracao, lista_lim, gif_url
    Campos podem ser None ou string vazia quando ausentes; lista_lim é lista.
    """
    texto, gif = limpar_html_e_extrair_gif(desc_raw or "")
    if not texto:
        return "", "", "", "", "", [], gif

    def pegar(rotulos):
        for r in rotulos:
            pad = rf"(?:^|\n){re.escape(r)}\s*:\s*(.+?)(?:\n|$)"
            m = re.search(pad, texto, flags=re.IGNORECASE | re.MULTILINE)
            if m:
                return m.group(1).strip()
        return None

    efeito = pegar(["Efeito", "Effect"])
    custo = pegar(["Custo", "Mana", "Cost", "Custo de mana"])
    cooldown = pegar(["Cooldown", "CD"])
    duracao = pegar(["Duração", "Duracao", "Duration"])
    limitacoes_raw = pegar(["Limitações", "Limitacoes", "Limitações", "Restricoes", "Restrições", "Restriçoes", "Restrições"])

    # descrição base: texto antes de "Efeito:" (se existir), senão todo o texto
    parts = re.split(r"(?:^|\n)Efeito\s*:", texto, flags=re.IGNORECASE)
    desc_base = parts[0].strip() if parts else texto.strip()

    # formatar lista de limitações
    lista_lim = []
    if limitacoes_raw:
        for line in re.split(r"[\.\n]", limitacoes_raw):
            ln = line.strip()
            if ln:
                lista_lim.append(ln)

    # garantir strings (não None) para campos utilizados
    efeito = efeito or ""
    custo = custo or ""
    cooldown = cooldown or ""
    duracao = duracao or ""

    return desc_base, efeito, custo, cooldown, duracao, lista_lim, gif

# -------------------------
# CARREGAR E NORMALIZAR JSON
# -------------------------
ARQUIVO_JSON = "grimorio_completo.json"
try:
    with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
        dados = json.load(f)
except Exception as e:
    print(f"❌ Erro ao carregar JSON '{ARQUIVO_JSON}': {e}")
    dados = []

MAGIAS = []

def normalize_spell_obj(m):
    # garantir chaves base (title/name/titulo/nome)
    title = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or "Sem Título"

    # element: tentar várias chaves
    raw_element = m.get("element") or m.get("elemento") or m.get("tipo") or ""
    element_clean, icon = get_element_icon(raw_element)

    # description (pode ser html)
    desc = m.get("description") or m.get("descricao") or m.get("desc") or ""

    # categories
    cats_raw = m.get("categories") or m.get("categorias") or m.get("tags") or []
    cats = normalize_categories(cats_raw)

    # retornar objeto padronizado
    return {
        "title": title,
        "element_raw": raw_element,
        "element": element_clean,
        "icon": icon,
        "description": desc,
        "categories": cats,
        # manter também o objeto original para referência, se precisar
        "_orig": m
    }

# aceitar formato "blocos por elemento" (ex: [{ "element": "fire", "magias": [...] }, ...])
if isinstance(dados, list) and dados and isinstance(dados[0], dict) and "magias" in dados[0]:
    for bloco in dados:
        elem = bloco.get("element") or bloco.get("elemento") or ""
        for m in bloco.get("magias", []):
            if "element" not in m and "elemento" not in m:
                m["element"] = elem
            MAGIAS.append(normalize_spell_obj(m))
else:
    # lista direta de magias (cada item um spell)
    if isinstance(dados, list):
        for m in dados:
            if isinstance(m, dict):
                MAGIAS.append(normalize_spell_obj(m))

print(f"✅ Total de magias indexadas: {len(MAGIAS)}")

# -------------------------
# BOT DISCORD (SINGLE FILE)
# -------------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# autocomplete precisa do mesmo nome de parâmetro usado no decorator
async def autocomplete_magias(interaction: discord.Interaction, current: str):
    norm_cur = clean_string(current or "")
    choices = []
    for m in MAGIAS:
        titulo = m["title"] or ""
        if norm_cur in clean_string(titulo):
            # app_commands.Choice aceita name e value strings
            choices.append(app_commands.Choice(name=titulo[:100], value=titulo))
        if len(choices) >= 25:
            break
    return choices

@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.autocomplete(nome=autocomplete_magias)
async def cmd_magia(interaction: discord.Interaction, nome: str):
    alvo = clean_string(nome or "")
    found = None
    for m in MAGIAS:
        if clean_string(m["title"]) == alvo:
            found = m
            break

    if not found:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    # extrair campos da description
    desc_raw = found["description"] or ""
    desc_clean, efeito, custo, cooldown, duracao, lista_lim, gif = extrair_campos_da_descricao(desc_raw)

    titulo = found["title"]
    elemento_cap = found["element"].capitalize() if found["element"] else (clean_string(found["element_raw"]).capitalize() or "Desconhecido")
    emoji = found["icon"] or "❔"
    categorias_text = ", ".join(found["categories"]) if found["categories"] else "Nenhuma"

    # limitar textos para embed
    def trunc(t, lim=1024):
        if not t:
            return ""
        t = str(t)
        return t if len(t) <= lim else t[:lim-3] + "..."

    desc_clean = trunc(desc_clean) or "Sem descrição."
    efeito = trunc(efeito) or "Sem efeito."
    limitacoes_text = "\n".join(f"- {l}" for l in lista_lim) if lista_lim else "Nenhuma."

    embed = discord.Embed(title=f"{emoji} {titulo}", color=discord.Color.orange())
    embed.add_field(name="🔷 Elemento", value=f"{emoji} {elemento_cap}", inline=False)
    embed.add_field(name="📜 Descrição", value=desc_clean, inline=False)
    embed.add_field(name="🎯 Efeito", value=efeito, inline=False)
    embed.add_field(name="💧 Custo", value=trunc(custo) or "?", inline=True)
    embed.add_field(name="⏳ Cooldown", value=trunc(cooldown) or "?", inline=True)
    embed.add_field(name="⌛ Duração", value=trunc(duracao) or "?", inline=True)
    embed.add_field(name="⚠️ Limitações", value=trunc(limitacoes_text), inline=False)
    embed.set_footer(text=f"Categorias: {categorias_text}")

    if gif:
        try:
            embed.set_image(url=gif)
        except Exception:
            pass

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buscar", description="Busca magias que contenham o termo no nome ou descrição.")
@app_commands.describe(term="Palavra ou parte da magia para buscar")
async def cmd_buscar(interaction: discord.Interaction, term: str):
    norm_term = clean_string(term or "")
    encontrados = []
    for m in MAGIAS:
        titulo = m["title"] or ""
        desc = m["description"] or ""
# --- BUSCA APRIMORADA ---
cats = " ".join(m["categories"]) if m["categories"] else ""

if (
    norm_term in clean_string(titulo) or
    norm_term in clean_string(desc) or
    norm_term in clean_string(cats)
):
    encontrados.append(titulo)

    if not encontrados:
        await interaction.response.send_message(f"❌ Nenhuma magia encontrada para \"{term}\".", ephemeral=True)
        return

    texto = "\n".join(f"• {t}" for t in sorted(encontrados))
    texto = texto[:1024]
    embed = discord.Embed(title=f"🔍 Resultados da busca ({len(encontrados)})", description=texto, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

# evento ready
@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user}")
    try:
        await bot.tree.sync()
        print("✅ Comandos sincronizados.")
    except Exception as e:
        print("❌ Erro ao sincronizar comandos:", e)

# iniciar tudo
if __name__ == "__main__":
    # inicia keepalive em thread
    threading.Thread(target=run_flask, daemon=True).start()

    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Token do Discord não configurado! Defina DISCORD_TOKEN nas variáveis de ambiente.")
    else:
        bot.run(TOKEN)

