# bot_grimorio.py
import os
import json
import re
import threading
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------
# Config / Intents
# ---------------------------
intents = discord.Intents.default()
# message_content não é necessário para slash commands, mantemos False por segurança
intents.message_content = False

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------
# Keep-alive Flask (Render)
# ---------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Grimório ativo!"

def run_flask():
    # roda Flask em thread separada para manter Render satisfeito
    app.run(host="0.0.0.0", port=8080)

# ---------------------------
# Util: limpeza e parsing
# ---------------------------
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
    return txt if len(txt) <= limite else txt[:limite - 3].rstrip() + "..."

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
    # Efeito
    m = re.search(r'(?im)^\s*Efeito\s*:\s*(.+?)(?:\n|$)', desc)
    if m:
        efeito = m.group(1).strip()
        desc = re.sub(r'(?im)^\s*Efeito\s*:\s*.+?(?:\n|$)', '', desc, count=1)
    # Limitações
    m2 = re.search(r'(?im)^\s*Limitaç(?:ões|oes)\s*:\s*(.+?)(?:\n|$)', desc)
    if m2:
        limitacoes = m2.group(1).strip()
        desc = re.sub(r'(?im)^\s*Limitaç(?:ões|oes)\s*:\s*.+?(?:\n|$)', '', desc, count=1)
    return efeito, limitacoes, desc.strip()

def normalizar_magia(raw):
    """
    Converte um item raw do JSON em formato padronizado:
    { nome, descricao, elemento, efeito, custo, cooldown, duracao, limitacoes, categorias }
    Aceita chaves em pt/en (title/description, nome/descricao, element/elemento, categories/categorias).
    """
    nome = raw.get("nome") or raw.get("title") or raw.get("Titulo") or raw.get("titulo") or "Sem nome"
    descricao_raw = raw.get("descricao") or raw.get("description") or raw.get("desc") or ""
    elemento = raw.get("elemento") or raw.get("element") or "Desconhecido"
    categorias = raw.get("categorias") or raw.get("categories") or []

    descricao = limpar_html(descricao_raw)

    custo = raw.get("custo") or raw.get("cost")
    cooldown = raw.get("cooldown") or raw.get("recarga")
    duracao = raw.get("duracao") or raw.get("duration")
    efeito = raw.get("efeito") or raw.get("effect")
    limitacoes = raw.get("limitacoes") or raw.get("limitations")

    # Extrai de labels dentro da descrição caso estejam lá
    if not custo:
        custo, descricao = extrair_valor_por_label(descricao, ["Custo", "Cost"])
    if not cooldown:
        cooldown, descricao = extrair_valor_por_label(descricao, ["Cooldown", "Recarga"])
    if not duracao:
        duracao, descricao = extrair_valor_por_label(descricao, ["Duração", "Duracao", "Duration"])
    if not efeito or not limitacoes:
        e, l, descricao = extrair_efeito_lim(descricao)
        efeito = efeito or e
        limitacoes = limitacoes or l

    # Limpa prefixos redundantes
    descricao = re.sub(r'(?im)^Descrição\s*:\s*', '', descricao).strip()
    descricao = re.sub(r'(?im)^Description\s*:\s*', '', descricao).strip()

    return {
        "nome": str(nome).strip(),
        "descricao": descricao or "Sem descrição.",
        "elemento": elemento,
        "efeito": efeito or "Sem efeito.",
        "custo": custo or "N/A",
        "cooldown": cooldown or "N/A",
        "duracao": duracao or "N/A",
        "limitacoes": limitacoes or "Nenhuma.",
        "categorias": categorias or []
    }

def build_embed_from_magia(m):
    embed = discord.Embed(title=f"✨ {m['nome']}", color=discord.Color.orange())
    embed.add_field(name="📘 Elemento", value=m["elemento"], inline=False)
    embed.add_field(name="📜 Descrição", value=limitar_texto(m["descricao"]), inline=False)
    if m.get("efeito"):
        embed.add_field(name="🎯 Efeito", value=limitar_texto(m["efeito"]), inline=False)
    embed.add_field(name="💧 Custo", value=str(m.get("custo", "N/A")), inline=True)
    embed.add_field(name="⏳ Cooldown", value=str(m.get("cooldown", "N/A")), inline=True)
    embed.add_field(name="🕓 Duração", value=str(m.get("duracao", "N/A")), inline=True)
    if m.get("limitacoes"):
        embed.add_field(name="⚠️ Limitações", value=limitar_texto(m.get("limitacoes")), inline=False)
    categorias = ", ".join(m.get("categorias", [])) if m.get("categorias") else "—"
    embed.set_footer(text=f"Categorias: {categorias}")
    return embed

# ---------------------------
# Carregar JSON do grimório
# ---------------------------
JSON_FILE = "grimorio_completo.json"

MAGIAS = []
MAGIA_MAP = {}

try:
    if not os.path.exists(JSON_FILE):
        raise FileNotFoundError(f"{JSON_FILE} não encontrado no diretório do projeto.")
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Caso o JSON esteja agrupado por elementos, tenta achá-las
    entries = []
    if isinstance(raw, dict):
        # pode ser {"Fogo": {"magias": [...]}, ...} ou {"magias": [...]}
        if "magias" in raw and isinstance(raw["magias"], list):
            entries = raw["magias"]
        else:
            # percorre e recolhe listas
            for v in raw.values():
                if isinstance(v, list):
                    entries.extend(v)
                elif isinstance(v, dict) and "magias" in v and isinstance(v["magias"], list):
                    entries.extend(v["magias"])
    elif isinstance(raw, list):
        entries = raw
    else:
        entries = []

    MAGIAS = [normalizar_magia(item) for item in entries]
    MAGIA_MAP = {m["nome"].lower(): m for m in MAGIAS if m.get("nome")}
    print(f"✅ JSON carregado e normalizado: {len(MAGIAS)} magias indexadas.")
except Exception as e:
    print(f"❌ Erro ao carregar {JSON_FILE}: {e}")
    MAGIAS = []
    MAGIA_MAP = {}

# ---------------------------
# Autocomplete (async)
# ---------------------------
async def autocomplete_magia(interaction: discord.Interaction, current: str):
    try:
        current = (current or "").strip().lower()
        choices = []
        for m in MAGIAS:
            nome = m.get("nome", "")
            if current in nome.lower():
                # nome deve ter 1..100 chars (Discord)
                display = nome if len(nome) <= 100 else nome[:97] + "..."
                choices.append(app_commands.Choice(name=display, value=nome))
            if len(choices) >= 25:
                break
        if not choices:
            # devolve uma opção neutra — não deixe value vazio porque o comando precisa de valor
            choices.append(app_commands.Choice(name="Nenhuma magia encontrada", value="__NENHUMA__"))
        return choices
    except Exception as exc:
        print("Erro no autocomplete:", exc)
        return [app_commands.Choice(name="Erro", value="__ERRO__")]

# ---------------------------
# Slash command /magia
# ---------------------------
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.describe(nome="Nome da magia a ser consultada.")
@app_commands.autocomplete(nome=autocomplete_magia)
async def comando_magia(interaction: discord.Interaction, nome: str):
    # Se a autocomplete retornou placeholder
    if not nome or nome in ("__NENHUMA__", "__ERRO__"):
        await interaction.response.send_message("❌ Nenhuma magia selecionada.", ephemeral=True)
        return

    chave = nome.strip().lower()
    magia = MAGIA_MAP.get(chave)
    if not magia:
        # tenta buscar por similaridade simples (contains)
        found = None
        for m in MAGIAS:
            if chave in m.get("nome", "").lower():
                found = m
                break
        if found:
            magia = found
        else:
            await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
            print(f"Magia não encontrada: {nome}")
            return

    embed = build_embed_from_magia(magia)
    try:
        await interaction.response.send_message(embed=embed)
        print(f"✅ Enviado embed da magia: {magia.get('nome')}")
    except Exception as e:
        print(f"❌ Erro ao enviar embed para {magia.get('nome')}: {e}")
        # tenta enviar texto simples como fallback
        try:
            texto = f"**{magia.get('nome')}**\n{magia.get('descricao')}\n\nCusto: {magia.get('custo')} • Cooldown: {magia.get('cooldown')} • Duração: {magia.get('duracao')}"
            await interaction.response.send_message(texto, ephemeral=True)
        except Exception as e2:
            print("Fallback também falhou:", e2)

# ---------------------------
# Eventos do bot
# ---------------------------
@bot.event
async def on_ready():
    print(f"🪄 Bot conectado como {bot.user} — sincronizando comandos...")
    try:
        synced = await bot.tree.sync()
        print(f"📜 {len(synced)} comandos sincronizados.")
    except Exception as e:
        print("❌ Erro ao sincronizar comandos:", e)

# ---------------------------
# Ler token (aceita TOKEN ou discord_token)
# ---------------------------
def obter_token_do_ambiente():
    # aceita maiúsculas/minúsculas e ambos nomes
    token = os.getenv("TOKEN") or os.getenv("token") or os.getenv("discord_token") or os.getenv("DISCORD_TOKEN")
    if token:
        # print mascarado para garantir que algo foi lido (não revele token)
        shown = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "****"
        print(f"🔐 Token lido das variáveis de ambiente (mascarado): {shown} (len={len(token)})")
    else:
        print("⚠️ Nenhum token de bot encontrado nas variáveis de ambiente (procurado: TOKEN, discord_token, DISCORD_TOKEN).")
    return token

# ---------------------------
# Start
# ---------------------------
if __name__ == "__main__":
    # Start Flask thread
    threading.Thread(target=run_flask, daemon=True).start()

    TOKEN = obter_token_do_ambiente()
    if not TOKEN:
        print("❌ Erro crítico: Token ausente. Configure a variável de ambiente `TOKEN` ou `discord_token` no Render.")
        # mantém o processo vivo por debug (Render mostrará a mensagem), mas encerra para evitar loops
        raise SystemExit(1)

    try:
        print("🚀 Iniciando bot — conectando ao Discord...")
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("❌ LoginFailure: Token inválido. Verifique se o token está correto e atualizado no Developer Portal e nas variáveis do Render.")
        raise
    except Exception as e:
        print("❌ Erro inesperado ao iniciar o bot:", e)
        raise
