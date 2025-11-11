import discord
from discord.ext import commands
from discord import app_commands
import json
import re
from flask import Flask
import threading

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("❌ Erro: Token do bot não encontrado nas variáveis de ambiente.")
    exit()
# ------------------------------------------------------------
# CONFIGURAÇÃO DO BOT
# ------------------------------------------------------------

# ------------------------------------------------------------
# FLASK (para manter o Render ativo)
# ------------------------------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Grimório ativo!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# ------------------------------------------------------------
# FUNÇÕES DE TRATAMENTO DE TEXTO
# ------------------------------------------------------------
def limpar_html(texto: str) -> str:
    if not texto:
        return ""
    texto = str(texto)
    texto = re.sub(r'<\s*br\s*/?\s*>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = re.sub(r'\r\n|\r', '\n', texto)
    texto = re.sub(r'\n{2,}', '\n\n', texto)
    return texto.strip()

def limitar_texto(txt, limite=1024):
    if not txt:
        return "—"
    txt = str(txt).strip()
    return txt if len(txt) <= limite else txt[:limite - 3] + "..."

def extrair_valor_por_label(desc: str, labels):
    if not desc:
        return None, desc
    for label in labels:
        m = re.search(rf'(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*(?:\n|$)', desc)
        if m:
            val = m.group(1).strip()
            desc = re.sub(rf'(?im)^\s*{re.escape(label)}\s*:\s*.+?(?:\n|$)', '', desc, count=1)
            return val, desc.strip()
    return None, desc

def extrair_efeito_lim(desc: str):
    efeito, limitacoes = None, None
    m = re.search(r'(?im)Efeito\s*:\s*(.+?)(?:\n|$)', desc)
    if m:
        efeito = m.group(1).strip()
        desc = re.sub(r'(?im)Efeito\s*:\s*.+?(?:\n|$)', '', desc)
    m2 = re.search(r'(?im)Limitaç(?:ões|oes)\s*:\s*(.+?)(?:\n|$)', desc)
    if m2:
        limitacoes = m2.group(1).strip()
        desc = re.sub(r'(?im)Limitaç(?:ões|oes)\s*:\s*.+?(?:\n|$)', '', desc)
    return efeito, limitacoes, desc.strip()

def normalizar_magia(raw):
    nome = raw.get("nome") or raw.get("title") or "Sem nome"
    descricao_raw = raw.get("descricao") or raw.get("description") or "Sem descrição."
    elemento = raw.get("elemento") or raw.get("element") or "Desconhecido"
    categorias = raw.get("categorias") or raw.get("categories") or []

    descricao = limpar_html(descricao_raw)
    custo = raw.get("custo")
    cooldown = raw.get("cooldown")
    duracao = raw.get("duracao")
    efeito = raw.get("efeito")
    limitacoes = raw.get("limitacoes")

    if not custo:
        custo, descricao = extrair_valor_por_label(descricao, ["Custo", "Cost"])
    if not cooldown:
        cooldown, descricao = extrair_valor_por_label(descricao, ["Cooldown", "Recarga"])
    if not duracao:
        duracao, descricao = extrair_valor_por_label(descricao, ["Duração", "Duration"])
    if not efeito or not limitacoes:
        e, l, descricao = extrair_efeito_lim(descricao)
        efeito = efeito or e
        limitacoes = limitacoes or l

    descricao = re.sub(r'(?im)^Descrição\s*:\s*', '', descricao).strip()

    return {
        "nome": nome.strip(),
        "descricao": descricao or "Sem descrição.",
        "elemento": elemento,
        "efeito": efeito or "Sem efeito.",
        "custo": custo or "N/A",
        "cooldown": cooldown or "N/A",
        "duracao": duracao or "N/A",
        "limitacoes": limitacoes or "Nenhuma.",
        "categorias": categorias
    }

def build_embed_from_magia(m):
    embed = discord.Embed(title=f"✨ {m['nome']}", color=discord.Color.orange())
    embed.add_field(name="📘 Elemento", value=m["elemento"], inline=False)
    embed.add_field(name="📜 Descrição", value=limitar_texto(m["descricao"]), inline=False)
    embed.add_field(name="🎯 Efeito", value=limitar_texto(m["efeito"]), inline=False)
    embed.add_field(name="💧 Custo", value=m["custo"], inline=True)
    embed.add_field(name="⏳ Cooldown", value=m["cooldown"], inline=True)
    embed.add_field(name="🕓 Duração", value=m["duracao"], inline=True)
    embed.add_field(name="⚠️ Limitações", value=limitar_texto(m["limitacoes"]), inline=False)
    categorias = ", ".join(m["categorias"]) if m["categorias"] else "—"
    embed.set_footer(text=f"Categorias: {categorias}")
    return embed

# ------------------------------------------------------------
# CARREGAR O JSON
# ------------------------------------------------------------
try:
    with open("grimorio_completo.json", "r", encoding="utf-8") as f:
        raw_list = json.load(f)
    MAGIAS = [normalizar_magia(r) for r in raw_list]
    MAGIA_MAP = {m["nome"].lower(): m for m in MAGIAS}
    print(f"✅ JSON carregado: {len(MAGIAS)} magias disponíveis.")
except Exception as e:
    print(f"❌ Erro ao carregar JSON: {e}")
    MAGIAS = []
    MAGIA_MAP = {}

# ------------------------------------------------------------
# AUTOCOMPLETE
# ------------------------------------------------------------
@app_commands.autocomplete(nome=None)
async def autocomplete_magia(interaction: discord.Interaction, current: str):
    results = [
        app_commands.Choice(name=m["nome"], value=m["nome"])
        for m in MAGIAS if current.lower() in m["nome"].lower()
    ][:20]
    return results

# ------------------------------------------------------------
# COMANDO /MAGIA
# ------------------------------------------------------------
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.describe(nome="Nome da magia a ser consultada.")
@app_commands.autocomplete(nome=autocomplete_magia)
async def comando_magia(interaction: discord.Interaction, nome: str):
    magia = MAGIA_MAP.get(nome.lower())
    if not magia:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return
    embed = build_embed_from_magia(magia)
    await interaction.response.send_message(embed=embed)

# ------------------------------------------------------------
# EVENTOS DO BOT
# ------------------------------------------------------------
@bot.event
async def on_ready():
    print(f"🚀 Iniciando Grimório como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"📜 Comandos sincronizados: {len(synced)} disponíveis.")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")

# ------------------------------------------------------------
# INICIAR
# ------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(TOKEN)

