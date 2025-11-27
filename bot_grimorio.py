import discord
from discord import app_commands
from discord.ext import commands
import json
import re
import os
from flask import Flask
import threading

# ===== CONFIGURAÇÃO FLASK PARA MANTER ONLINE =====
app = Flask(__name__)

@app.route("/")
def home():
    return "🪄 Grimório ativo!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ===== FUNÇÕES AUXILIARES =====
def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""
    return re.sub(r"[^a-z0-9]", "", texto.lower())

def limpar_html(texto: str) -> str:
    if not texto:
        return ""
    # remove imagens
    texto = re.sub(r"<img[^>]*>", "", texto, flags=re.IGNORECASE)
    # remove tags HTML gerais
    texto = re.sub(r"</?(p|div|span|strong|em|b|i|u|br)[^>]*>", "\n", texto, flags=re.IGNORECASE)
    # substitui múltiplas quebras por duas
    texto = re.sub(r"\n{2,}", "\n\n", texto)
    return texto.strip()

def extrair_campos(desc: str):
    s = limpar_html(desc)

    # regex tolerante para capturar os campos
    def busca(pads):
        m = re.search(pads, s, flags=re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else None

    efeito = busca(r"(?:^|\n)Efeito\s*:\s*(.+?)(?:\n|$)")
    custo = busca(r"(?:^|\n)Custo\s*:\s*(.+?)(?:\n|$)")
    cooldown = busca(r"(?:^|\n)Cooldown\s*:\s*(.+?)(?:\n|$)")
    duracao = busca(r"(?:^|\n)Dura(?:ç|c)[aã]o\s*:\s*(.+?)(?:\n|$)")
    lim = busca(r"(?:^|\n)Limita(?:ç|c)[oõ]es\s*:\s*(.+?)(?:\n|$)")

    # extrair texto base da descrição sem os campos extras
    # (remover tudo desde "Efeito:" pra frente)
    desc_base = re.split(r"(?:\n|^)Efeito\s*:", s, flags=re.IGNORECASE)[0].strip()

    # processar limitações em linhas separadas
    lims = []
    if lim:
        for line in re.split(r"\.|\n", lim):
            line = line.strip()
            if line:
                lims.append(line)

    return {
        "descricao": desc_base or None,
        "efeito": efeito,
        "custo": custo,
        "cooldown": cooldown,
        "duracao": duracao,
        "limitacoes": lims if lims else None
    }

# ===== CARREGAR JSON =====
ARQUIVO_JSON = "grimorio_completo.json"
try:
    with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
        dados = json.load(f)
except Exception as e:
    print(f"❌ Erro ao carregar JSON: {e}")
    dados = []

MAGIAS = []
if isinstance(dados, list) and dados and isinstance(dados[0], dict) and "magias" in dados[0]:
    for bloco in dados:
        for m in bloco.get("magias", []):
            # Preenche elemento se estiver no bloco mas não na magia
            if "element" not in m and "elemento" not in m:
                m["element"] = bloco.get("element") or bloco.get("elemento") or ""
            MAGIAS.append(m)
else:
    MAGIAS = dados

print(f"✅ Total de magias indexadas: {len(MAGIAS)}")

# ===== EMOJIS POR ELEMENTO =====
EMOJI_ELEMENTOS = {
    "fire": "🔥", "fogo": "🔥",
    "water": "💧", "água": "💧", "agua": "💧",
    "earth": "🌱", "terra": "🌱",
    "air": "🌪️", "ar": "🌪️",
    "light": "✨", "luz": "✨",
    "dark": "🌑", "escuridão": "🌑", "escuro": "🌑",
    "arcano": "🔮", "dimensional": "🌀", "time": "⌛", "tempo": "⌛",
    "status": "💠", "unknown": "❔"
}

def emoji_elemento(el_raw: str):
    if not el_raw:
        return EMOJI_ELEMENTOS.get("unknown", "❔")
    key = el_raw.lower().strip()
    return EMOJI_ELEMENTOS.get(key, EMOJI_ELEMENTOS.get(key.split()[0], "❔"))

# ===== BOT DISCORD =====
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== AUTOCOMPLETE PARA /magia =====
async def autocomplete_magias(interaction: discord.Interaction, current: str):
    choices = []
    norm_cur = normalizar_texto(current)
    for m in MAGIAS:
        titulo = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or ""
        if norm_cur in normalizar_texto(titulo):
            choices.append(app_commands.Choice(name=str(titulo)[:100], value=str(titulo)))
        if len(choices) >= 25:
            break
    return choices

# ===== COMANDO /magia =====
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.autocomplete(nome=autocomplete_magias)
async def cmd_magia(interaction: discord.Interaction, nome: str):
    magia = None
    norm_target = normalizar_texto(nome)
    for m in MAGIAS:
        titulo = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or ""
        if normalizar_texto(titulo) == norm_target:
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

    # Montar texto de limitações
    if lista_lim:
        limitacoes_text = "\n".join(f"- {l}" for l in lista_lim)
    else:
        limitacoes_text = "Nenhuma."

    # Truncar para não ultrapassar 1024 por campo, conforme limite de embed do Discord
    # Limite de valor de campo embed: 1024 caracteres. :contentReference[oaicite:0]{index=0}
    def truncar(texto: str, limite: int = 1024):
        if len(texto) > limite:
            return texto[: limite - 3] + "..."
        return texto

    desc_clean = truncar(desc_clean)
    efeito = truncar(efeito)
    limitacoes_text = truncar(limitacoes_text)

    embed = discord.Embed(title=f"{emoji} {titulo}", color=discord.Color.orange())
    embed.add_field(name="🔷 Elemento", value=f"{emoji} {elemento_cap}", inline=False)
    embed.add_field(name="📜 Descrição", value=desc_clean or "Sem descrição.", inline=False)
    embed.add_field(name="🎯 Efeito", value=efeito or "Sem efeito.", inline=False)
    embed.add_field(name="💧 Custo", value=str(custo), inline=True)
    embed.add_field(name="⏳ Cooldown", value=str(cooldown), inline=True)
    embed.add_field(name="⌛ Duração", value=str(duracao), inline=True)
    embed.add_field(name="⚠️ Limitações", value=limitacoes_text, inline=False)
    embed.set_footer(text=f"Categorias: {categorias_text}")

    if gif_url:
        embed.set_image(url=gif_url)

    await interaction.response.send_message(embed=embed)

# ===== COMANDO /buscar =====
@bot.tree.command(name="buscar", description="Busca magias que contenham o termo no nome ou descrição.")
@app_commands.describe(term="Palavra ou parte da magia para buscar")
async def cmd_buscar(interaction: discord.Interaction, term: str):
    norm_term = normalizar_texto(term)
    encontrados = []
    for m in MAGIAS:
        titulo = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or ""
        desc = m.get("description") or m.get("descricao") or ""
        if norm_term in normalizar_texto(titulo) or norm_term in normalizar_texto(desc):
            encontrados.append(titulo)
        if len(encontrados) >= 25:
            break

    if not encontrados:
        await interaction.response.send_message(f"❌ Nenhuma magia encontrada para \"{term}\".", ephemeral=True)
        return

    texto = "\n".join(f"• {t}" for t in sorted(encontrados))
    texto = texto[:1024]  # truncar para descrição de embed se necessário
    embed = discord.Embed(title=f"🔍 Resultados da busca ({len(encontrados)})", description=texto, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

# ===== INICIAR BOT E FLASK =====
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
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Token do Discord não configurado! Defina DISCORD_TOKEN nas variáveis de ambiente.")
    else:
        bot.run(TOKEN)

