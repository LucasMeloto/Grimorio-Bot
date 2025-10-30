import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from flask import Flask
import threading
import logging
import unicodedata
import pathlib

# =====================================================
# 🧩 CONFIGURAÇÃO DE LOGS
# =====================================================
logging.basicConfig(level=logging.INFO)

# =====================================================
# 🔹 NORMALIZAÇÃO DO JSON (aceita vários formatos)
# =====================================================

def normalize_entry(raw):
    """Converte qualquer entrada do JSON para o formato padrão usado pelo bot."""
    def pick(d, *keys, default=""):
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return default

    titulo = pick(raw, "titulo", "title", "nome", "name")
    descricao = pick(raw, "descricao", "description", "desc")
    efeito = pick(raw, "efeito", "effect", "details")
    custo = pick(raw, "custo", "cost", "mana")
    cooldown = pick(raw, "cooldown", "cd")
    duracao = pick(raw, "duracao", "duration")
    limitacoes = pick(raw, "limitações", "limitacoes", "limitations", "limits")
    elemento = pick(raw, "elemento", "element", "categoria", "categories")

    # Se "elemento" for lista, pega o primeiro valor
    if isinstance(elemento, list) and elemento:
        elemento = elemento[0]

    return {
        "titulo": str(titulo).strip(),
        "descricao": str(descricao).strip(),
        "efeito": str(efeito).strip(),
        "custo": str(custo).strip(),
        "cooldown": str(cooldown).strip(),
        "duracao": str(duracao).strip(),
        "limitações": str(limitacoes).strip(),
        "elemento": str(elemento).strip()
    }

# =====================================================
# 🔹 CARREGA E NORMALIZA O ARQUIVO JSON
# =====================================================
try:
    with open("grimorio_completo.json", "r", encoding="utf-8") as f:
        raw = json.load(f)

    magias_normalizadas = []
    bad_entries = []

    if isinstance(raw, list):
        for item in raw:
            try:
                norm = normalize_entry(item)
                if norm["titulo"]:
                    magias_normalizadas.append(norm)
                else:
                    bad_entries.append(item)
            except Exception as e:
                bad_entries.append({"erro": str(e), "item": item})

    elif isinstance(raw, dict):
        # Caso o JSON esteja dividido por elementos
        for key, val in raw.items():
            if isinstance(val, list):
                for item in val:
                    try:
                        norm = normalize_entry(item)
                        if norm["titulo"]:
                            magias_normalizadas.append(norm)
                        else:
                            bad_entries.append(item)
                    except Exception as e:
                        bad_entries.append({"erro": str(e), "item": item})
    else:
        raise ValueError("Formato de grimorio_completo.json não reconhecido.")

    if bad_entries:
        debug_path = pathlib.Path("/tmp/debug_grimorio_bad.json")
        debug_path.write_text(json.dumps(bad_entries, ensure_ascii=False, indent=2), encoding="utf-8")
        logging.warning(f"{len(bad_entries)} magias com formato irregular foram ignoradas. Detalhes em /tmp/debug_grimorio_bad.json")

    logging.info(f"✅ {len(magias_normalizadas)} magias carregadas e normalizadas com sucesso.")

except Exception as e:
    logging.error(f"Erro ao carregar o JSON: {e}")
    magias_normalizadas = []

# =====================================================
# 🔹 FUNÇÃO DE BUSCA ROBUSTA
# =====================================================
def normalize_text(s):
    if not isinstance(s, str):
        s = str(s)
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))

def buscar_magia(nome):
    nome_norm = normalize_text(nome)
    # Busca exata
    for m in magias_normalizadas:
        if normalize_text(m.get("titulo", "")) == nome_norm:
            return m
    # Busca parcial
    for m in magias_normalizadas:
        if nome_norm in normalize_text(m.get("titulo", "")):
            return m
    # Busca por elemento
    for m in magias_normalizadas:
        if nome_norm in normalize_text(m.get("elemento", "")):
            return m
    return None

# =====================================================
# 🔹 CONFIGURAÇÃO DO BOT
# =====================================================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# =====================================================
# 🌐 FLASK (para manter online no Render)
# =====================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot do Grimório está ativo! 🔮"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# =====================================================
# 🪄 COMANDO SLASH /magia
# =====================================================
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.describe(nome="Nome da magia para consultar")
async def slash_magia(interaction: discord.Interaction, nome: str):
    magia = buscar_magia(nome)
    if not magia:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"✨ {magia['titulo']}",
        description=magia['descricao'],
        color=discord.Color.purple()
    )
    embed.add_field(name="📘 Elemento", value=magia['elemento'] or "Desconhecido", inline=False)
    embed.add_field(name="📜 Efeito", value=magia['efeito'] or "Sem efeito.", inline=False)
    embed.add_field(name="💧 Custo", value=magia['custo'] or "N/A", inline=True)
    embed.add_field(name="⏳ Cooldown", value=magia['cooldown'] or "N/A", inline=True)
    embed.add_field(name="🕓 Duração", value=magia['duracao'] or "N/A", inline=True)
    if magia["limitações"]:
        embed.add_field(name="⚠️ Limitações", value=magia['limitações'], inline=False)

    await interaction.response.send_message(embed=embed)

# =====================================================
# 🧙 COMANDO TEXTO !magia
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
    if magia.get("limitações"):
        msg += f"\n**Limitações:** {magia['limitações']}"

    await ctx.send(msg)

# =====================================================
# 🧭 COMANDO !ajuda
# =====================================================
@bot.command(name="ajuda")
async def ajuda(ctx):
    msg = (
        "🔮 **Comandos do Bot do Grimório**\n\n"
        "**/magia [nome]** → Busca magias com autocomplete.\n"
        "**!magia [nome]** → Busca magias por texto.\n"
        "**!ajuda** → Mostra esta mensagem."
    )
    await ctx.send(msg)

# =====================================================
# 🚀 EVENTO ON_READY
# =====================================================
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot do Grimório online como {bot.user}!")
        print(f"🔁 {len(synced)} comandos sincronizados com sucesso.")
    except Exception as e:
        print(f"⚠️ Erro ao sincronizar comandos: {e}")

# =====================================================
# 🧩 EXECUÇÃO
# =====================================================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(os.environ["DISCORD_TOKEN"])
