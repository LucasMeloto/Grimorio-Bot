import discord
from discord import app_commands
from discord.ext import commands
import json
import re
import os
from flask import Flask
import threading
import asyncio

# ==== CONFIGURAÇÃO FLASK PARA MANTER ONLINE ====
app = Flask(__name__)

@app.route('/')
def home():
    return "🪄 Grimório ativo!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==== FUNÇÕES AUXILIARES ====
def normalizar_texto(texto: str):
    if not texto:
        return ""
    return re.sub(r"[^a-z0-9]", "", texto.lower())

def limpar_html(texto: str):
    if not texto:
        return ""
    # remove tags img
    texto = re.sub(r"<img[^>]*>", "", texto, flags=re.IGNORECASE)
    # remove outras tags como <b>, <i>, etc
    texto = re.sub(r"<\/?[biu]>","", texto, flags=re.IGNORECASE)
    # replace <br> e variantes por nova linha
    texto = re.sub(r"<br\s*\/?>", "\n", texto, flags=re.IGNORECASE)
    # remove múltiplas quebras
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()

def extrair_campos_da_descricao(desc: str):
    """
    Retorna: (descricao_limpa, efeito, custo, cooldown, duracao, lista_limitações, gif_url)
    """
    descricao = desc or ""
    gif_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', descricao, flags=re.IGNORECASE)
    gif_url = gif_match.group(1) if gif_match else None

    # padrões principais
    padroes = {
        "custo": r'(?:^|\n)\s*(Custo|Cost)\s*:\s*(.+?)(?:\n|$)',
        "cooldown": r'(?:^|\n)\s*(Cooldown|Recarga)\s*:\s*(.+?)(?:\n|$)',
        "duracao": r'(?:^|\n)\s*(Dura[cç][aã]o|Duration)\s*:\s*(.+?)(?:\n|$)',
        "efeito": r'(?:^|\n)\s*(Efeito|Effect)\s*:\s*(.+?)(?:\n|$)',
        "limitacoes": r'(?:^|\n)\s*(Limita[cç][oõ]es|Limitations)\s*:\s*(.+?)(?:\n|$)'
    }

    encontrados = {k: None for k in padroes.keys()}

    for chave, patt in padroes.items():
        m = re.search(patt, descricao, flags=re.IGNORECASE | re.DOTALL)
        if m:
            encontrados[chave] = m.group(2).strip()
            descricao = re.sub(patt, "\n", descricao, flags=re.IGNORECASE | re.DOTALL)

    descricao_limpa = limpar_html(descricao)

    # tratamento de limitações como lista
    lim_raw = encontrados.get("limitacoes")
    if lim_raw:
        lista_lim = [l.strip() for l in lim_raw.splitlines() if l.strip()]
    else:
        lista_lim = []

    return (
        descricao_limpa,
        encontrados.get("efeito") or "",
        encontrados.get("custo") or "N/A",
        encontrados.get("cooldown") or "N/A",
        encontrados.get("duracao") or "N/A",
        lista_lim,
        gif_url
    )

# ==== CARREGAR JSON ====
ARQUIVO_JSON = "grimorio_completo.json"
try:
    with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
        dados = json.load(f)
except Exception as e:
    print(f"❌ Erro ao carregar JSON: {e}")
    dados = []

# Desdobrar se for por elemento → magias
MAGIAS = []
if isinstance(dados, list) and dados and "magias" in dados[0]:
    for elem_block in dados:
        for m in elem_block.get("magias", []):
            # preenche elemento se não existir
            if "element" not in m and "elemento" not in m:
                m["element"] = elem_block.get("element") or elem_block.get("elemento") or ""
            MAGIAS.append(m)
else:
    MAGIAS = dados

print(f"✅ Total de magias indexadas: {len(MAGIAS)}")

# ==== EMOJIS POR ELEMENTO ====
EMOJI_ELEMENTOS = {
    "fire": "🔥", "fogo": "🔥",
    "water": "💧", "água": "💧", "agua": "💧",
    "earth": "🌱", "terra": "🌱",
    "ar": "🌪️", "air": "🌪️",
    "light": "✨", "luz": "✨",
    "dark": "🌑", "escuridão": "🌑", "escuro": "🌑",
    "arcano": "🔮", "arcane": "🔮",
    "dimensional": "🌀",
    "time": "⌛", "tempo": "⌛",
    "status": "💠",
    "none": "⚪", "unknown": "❔"
}

def emoji_elemento(elemento_raw):
    if not elemento_raw:
        return EMOJI_ELEMENTOS.get("unknown", "❔")
    key = elemento_raw.lower().strip()
    return EMOJI_ELEMENTOS.get(key, EMOJI_ELEMENTOS.get(key.split()[0], "❔"))

# ==== AUTOCOMPLETE ====
async def autocomplete_magias(interaction: discord.Interaction, current: str):
    choices = []
    normalized_current = normalizar_texto(current)
    for m in MAGIAS:
        titulo = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or ""
        if normalized_current in normalizar_texto(str(titulo)):
            choices.append(app_commands.Choice(name=str(titulo)[:100], value=str(titulo)))
        if len(choices) >= 25:
            break
    return choices

# ==== BOT DISCORD ====
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ==== COMANDO /magia ====
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.autocomplete(nome=autocomplete_magias)
async def cmd_magia(interaction: discord.Interaction, nome: str):
    magia = None
    normalized_target = normalizar_texto(nome)
    for m in MAGIAS:
        titulo = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or ""
        if normalizar_texto(titulo) == normalized_target:
            magia = m
            break

    if not magia:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    titulo = magia.get("title") or magia.get("titulo") or magia.get("name") or magia.get("nome") or "Sem nome"
    element_raw = magia.get("element") or magia.get("elemento") or ""
    elemento_cap = element_raw.capitalize() if element_raw else "Desconhecido"
    emoji = emoji_elemento(element_raw)

    descricao_raw = magia.get("description") or magia.get("descricao") or ""
    desc_clean, efeito, custo, cooldown, duracao, lista_lim, gif_url = extrair_campos_da_descricao(descricao_raw)

    categorias = magia.get("categories") or magia.get("categorias") or []
    categorias_text = ", ".join(categorias) if categorias else "Nenhuma"

    # Campos finais
    limitacoes_text = "\n".join(f"- {l}" for l in lista_lim) if lista_lim else "Nenhuma."

    embed = discord.Embed(title=f"{emoji} {titulo}", color=discord.Color.orange())
    embed.add_field(name="🔷 Elemento", value=f"{emoji} {elemento_cap}", inline=False)
    embed.add_field(name="📜 Descrição", value=desc_clean or "Sem descrição.", inline=False)
    embed.add_field(name="🎯 Efeito", value=efeito or "Sem efeito.", inline=False)
    embed.add_field(name="💧 Custo", value=custo, inline=True)
    embed.add_field(name="⏳ Cooldown", value=cooldown, inline=True)
    embed.add_field(name="⌛ Duração", value=duracao, inline=True)
    embed.add_field(name="⚠️ Limitações", value=limitacoes_text, inline=False)
    embed.set_footer(text=f"Categorias: {categorias_text}")

    if gif_url:
        embed.set_image(url=gif_url)

    await interaction.response.send_message(embed=embed)

# ==== COMANDO /listar ====
@bot.tree.command(name="listar", description="Lista as magias por elemento e tipo.")
async def cmd_listar(interaction: discord.Interaction, elemento: str = None):
    organizacao = {}
    for m in MAGIAS:
        elem = m.get("element") or m.get("elemento") or "Desconhecido"
        elem_cap = elem.capitalize()
        nivel = next((c for c in (m.get("categories") or m.get("categorias") or []) if c.lower() in ["básica", "basica", "intermediária", "intermediaria", "avançada", "avancada", "supremo"]), "Comum")
        organizacao.setdefault(elem_cap, {"Básica": [], "Intermediária": [], "Avançada": [], "Supremo": []})
        titulo = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or "Sem nome"
        if nivel.lower().startswith("sup"):
            organizacao[elem_cap]["Supremo"].append(titulo)
        elif nivel.lower().startswith("av"):
            organizacao[elem_cap]["Avançada"].append(titulo)
        elif nivel.lower().startswith("int"):
            organizacao[elem_cap]["Intermediária"].append(titulo)
        else:
            organizacao[elem_cap]["Básica"].append(titulo)

    # filtrar por elemento se fornecido
    if elemento:
        elem_key = elemento.capitalize()
        if elem_key not in organizacao:
            await interaction.response.send_message(f"❌ Elemento **{elemento}** não encontrado.", ephemeral=True)
            return
        grupos = {elem_key: organizacao[elem_key]}
    else:
        grupos = organizacao

    for elem, niveis in grupos.items():
        emoji = emoji_elemento(elem)
        embed = discord.Embed(title=f"{emoji} {elem}", color=discord.Color.dark_teal())
        for nivel, lista in niveis.items():
            if lista:
                embed.add_field(name=f"{nivel} ({len(lista)})", value="\n".join(sorted(lista))[:1024], inline=False)
        await interaction.channel.send(embed=embed)

    await interaction.response.send_message("📜 Magias listadas com sucesso!", ephemeral=True)

# ==== INICIAR BOT E FLASK ====
@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user}")
    try:
        await bot.tree.sync()
        print("✅ Comandos sincronizados.")
    except Exception as e:
        print("❌ Erro ao sincronizar comandos:", e)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    if not TOKEN:
        print("❌ Token do Discord não configurado! Defina DISCORD_TOKEN nas env vars.")
    else:
        bot.run(TOKEN)
