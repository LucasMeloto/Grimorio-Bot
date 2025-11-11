# bot_grimorio.py
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
import json
import os
import re
import threading
import asyncio

# ===== Flask simple (mantém serviço vivo) =====
app = Flask(__name__)

@app.route("/")
def home():
    return "🪄 Grimório ativo!"

def run_flask():
    # usa o servidor de desenvolvimento aqui (já funcionou pra você)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ===== Helpers =====
def normalizar_texto(t: str):
    if not t:
        return ""
    return re.sub(r'[^a-z0-9]', '', t.lower(), flags=re.IGNORECASE)

def extrair_campos_da_descricao(descricao_raw: str):
    """
    Extrai linhas como:
      Custo: 30 de mana
      Cooldown: 2 turnos
      Duração: 2 turnos
      Efeito: ...
    Remove essas linhas da descrição principal e retorna (descricao_limpa, efeito, custo, cooldown, duracao, gif_url)
    """
    descricao = descricao_raw or ""
    # encontrar gif em tag <img src="...">
    gif_match = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', descricao, flags=re.IGNORECASE)
    gif_url = gif_match.group(1) if gif_match else None

    # padrões possíveis (PT/EN)
    padroes = {
        "custo": r'(?:^|\n)\s*(Custo|Cost)\s*:\s*(.+?)(?:\n|$)',
        "cooldown": r'(?:^|\n)\s*(Cooldown|Recarga)\s*:\s*(.+?)(?:\n|$)',
        "duracao": r'(?:^|\n)\s*(Dura[cç][aã]o|Duration)\s*:\s*(.+?)(?:\n|$)',
        "efeito": r'(?:^|\n)\s*(Efeito|Effect)\s*:\s*(.+?)(?:\n|$)'
    }

    encontrado = {"custo": None, "cooldown": None, "duracao": None, "efeito": None}

    # busca cada padrão e remove da descrição
    for chave, patt in padroes.items():
        m = re.search(patt, descricao, flags=re.IGNORECASE | re.DOTALL)
        if m:
            # grupo 2 contém o conteúdo do campo
            encontrado[chave] = m.group(2).strip()
            # remove a linha inteira (para não repetir)
            descricao = re.sub(patt, "\n", descricao, flags=re.IGNORECASE | re.DOTALL)

    # também remover possíveis cabeçalhos como "Descrição:" ou "Efeito:" no corpo
    descricao = re.sub(r'\bDescrição\s*:\s*', '', descricao, flags=re.IGNORECASE)
    descricao = re.sub(r'\bDescri[çc][aã]o\s*:\s*', '', descricao, flags=re.IGNORECASE)

    # trim e normalização de múltiplas quebras de linha
    descricao_limpa = "\n".join([linha.rstrip() for linha in descricao.strip().splitlines() if linha.strip()])

    return descricao_limpa, encontrado["efeito"], encontrado["custo"], encontrado["cooldown"], encontrado["duracao"], gif_url

# ===== Carregar JSON (formato: array de objetos com "title","description","element","categories", possivelmente "magias" por elemento) =====
def carregar_magias_do_arquivo(nome_arquivo="grimorio_completo.json"):
    try:
        with open(nome_arquivo, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("❌ Erro ao abrir JSON:", e)
        return []

    # Detectar formato: se é uma lista de elementos com chave "magias", desdobrar para lista plana
    magias_flat = []
    if isinstance(data, list):
        # checar se elementos tem 'magias' (estrutura por elemento)
        if data and isinstance(data[0], dict) and "magias" in data[0]:
            for elemento_obj in data:
                element_name = elemento_obj.get("element", elemento_obj.get("elemento", "")) or elemento_obj.get("element", "")
                for m in elemento_obj.get("magias", []):
                    # garantir que campo element/elemento exista em cada magia
                    if "element" not in m and "elemento" not in m:
                        m["element"] = element_name
                    magias_flat.append(m)
        else:
            # lista plana de magias (cada item é uma magia)
            magias_flat = data
    else:
        print("⚠️ JSON não é uma lista. Estrutura inesperada.")
        return []

    print(f"✅ JSON carregado: {len(magias_flat)} magias disponíveis.")
    return magias_flat

MAGIAS = carregar_magias_do_arquivo()

# ===== Emojis por elemento (mapear várias possibilidades) =====
EMOJI_ELEMENTOS = {
    "fire": "🔥", "fogo": "🔥",
    "water": "💧", "água": "💧", "agua": "💧",
    "earth": "🌱", "terra": "🌱",
    "air": "💨", "ar": "💨",
    "light": "✨", "luz": "✨",
    "dark": "🌑", "escuro": "🌑", "escuridão": "🌑,",
    "arcane": "🔮", "arcano": "🔮",
    "dimensional": "🌀", "dimensional": "🌀",
    "time": "⏳", "tempo": "⏳",
    "status": "💠", "none": "⚪", "unknown": "❔"
}

def emoji_para_elemento(elemento_raw):
    if not elemento_raw:
        return EMOJI_ELEMENTOS.get("unknown", "❔")
    key = str(elemento_raw).lower().strip()
    return EMOJI_ELEMENTOS.get(key, EMOJI_ELEMENTOS.get(key.split()[0], "❔"))

# ===== Bot Discord =====
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Helper de busca que normaliza contra múltiplos campos
def buscar_magia_por_nome(nome):
    chave = normalizar_texto(nome)
    for m in MAGIAS:
        # aceitar tanto 'title' quanto 'title' em inglês/pt, e também 'name'...
        possiveis = []
        possiveis.append(m.get("title") or m.get("titulo") or m.get("name") or m.get("nome"))
        # caso o JSON use 'title' e 'description' como antes
        for p in possiveis:
            if p and normalizar_texto(str(p)) == chave:
                return m
    return None

# autocomplete do /magia
async def autocomplete_magias(interaction: discord.Interaction, current: str):
    choices = []
    cur_norm = normalizar_texto(current)
    for m in MAGIAS:
        titulo = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or "Sem título"
        if cur_norm in normalizar_texto(str(titulo)):
            choices.append(app_commands.Choice(name=str(titulo)[:100], value=str(titulo)))
        if len(choices) >= 25:
            break
    return choices

# ===== Comando /magia =====
@bot.tree.command(name="magia", description="Consulta uma magia do grimório.")
@app_commands.autocomplete(nome=autocomplete_magias)
async def cmd_magia(interaction: discord.Interaction, nome: str):
    magia = buscar_magia_por_nome(nome)
    if not magia:
        await interaction.response.send_message(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)
        return

    titulo = magia.get("title") or magia.get("titulo") or magia.get("name") or magia.get("nome") or "Sem nome"
    descricao_raw = magia.get("description") or magia.get("description_text") or magia.get("descricao") or magia.get("description") or ""
    element_raw = magia.get("element") or magia.get("elemento") or magia.get("element", "")
    categorias = magia.get("categories") or magia.get("categorias") or magia.get("categories", [])

    # extrair Efeito/Custo/Cooldown/Duração de dentro da descrição (se presentes)
    descricao_limpa, efeito_extra, custo_extra, cooldown_extra, duracao_extra, gif_url_from_desc = extrair_campos_da_descricao(descricao_raw)

    # preferir campos explícitos da magia, se existirem
    efeito = magia.get("effect") or magia.get("efeito") or efeito_extra or "Sem efeito."
    custo = magia.get("cost") or magia.get("custo") or custo_extra or "N/A"
    cooldown = magia.get("cooldown") or magia.get("recarga") or cooldown_extra or "N/A"
    duracao = magia.get("duration") or magia.get("duracao") or duracao_extra or "N/A"

    # Limitacões: aceitar várias chaves
    limitacoes = magia.get("limitations") or magia.get("limitacoes") or magia.get("limitations", [])
    if isinstance(limitacoes, str):
        # se for string, tentar separar por linhas
        limitacoes_list = [l.strip() for l in limitacoes.splitlines() if l.strip()]
    elif isinstance(limitacoes, list):
        limitacoes_list = limitacoes
    else:
        limitacoes_list = []

    # GIF: pode vir no campo gif explícito ou dentro da descrição (detectado acima)
    gif_url = magia.get("gif") or magia.get("gif_url") or gif_url_from_desc

    # Emoji do elemento
    emoji_elemento = emoji_para_elemento(element_raw)

    # Formata campos
    categorias_text = ", ".join(categorias) if categorias else "Nenhuma"
    limitacoes_text = "\n".join(f"- {l}" for l in limitacoes_list) if limitacoes_list else "Nenhuma."

    # Monta embed conforme modelo antigo (titulo com emoji do elemento + nome; depois Elemento em campo; descrição narrativa sem linhas de custo; campos separados)
    embed = discord.Embed(title=f"{emoji_elemento} {titulo}", color=discord.Color.orange())

    # Campo Elemento (sem emoji extra)
    elemento_display = (str(element_raw).capitalize() if element_raw else "Sem Elemento")
    embed.add_field(name="🔷 Elemento", value=f"{emoji_elemento} {elemento_display}", inline=False)

    # Descrição narrativa limpa
    descricao_para_embed = descricao_limpa if descricao_limpa else "Sem descrição."
    # limitar tamanho para campo embed (1024)
    embed.add_field(name="📜 Descrição", value=descricao_para_embed[:1024], inline=False)

    # Efeito
    embed.add_field(name="🎯 Efeito", value=str(efeito)[:1024], inline=False)

    # Custo / Cooldown / Duração - em linha
    embed.add_field(name="💧 Custo", value=str(custo)[:1024], inline=True)
    embed.add_field(name="⏱️ Cooldown", value=str(cooldown)[:1024], inline=True)
    embed.add_field(name="⌛ Duração", value=str(duracao)[:1024], inline=True)

    # Limitações e categorias
    embed.add_field(name="⚠️ Limitações", value=limitacoes_text[:1024], inline=False)
    embed.set_footer(text=f"Categorias: {categorias_text}")

    # GIF se existir
    if gif_url:
        # embed permite imagem única
        embed.set_image(url=gif_url)

    await interaction.response.send_message(embed=embed)

# ===== Comando /listar (por elemento e nível) =====
@bot.tree.command(name="listar", description="Lista magias por elemento e por nível (básica/intermediária/avançada).")
async def cmd_listar(interaction: discord.Interaction, elemento: str = None):
    # organiza por elemento -> níveis
    organizacao = {}
    for m in MAGIAS:
        elem = m.get("element") or m.get("elemento") or "Sem Elemento"
        elem_display = str(elem).capitalize()
        nivel = (m.get("nivel") or m.get("level") or m.get("level_name") or "Básica").capitalize()
        organizacao.setdefault(elem_display, {"Básica": [], "Intermediária": [], "Avançada": []})
        titulo = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or "Sem nome"
        # tentar classificar nível entre Básica/Intermediária/Avançada
        if nivel.lower().startswith("int") or "inter" in nivel.lower():
            organizacao[elem_display]["Intermediária"].append(titulo)
        elif nivel.lower().startswith("av") or "avanç" in nivel.lower() or "advanced" in nivel.lower():
            organizacao[elem_display]["Avançada"].append(titulo)
        else:
            organizacao[elem_display]["Básica"].append(titulo)

    # se elemento especificado, filtrar
    if elemento:
        key = str(elemento).capitalize()
        if key not in organizacao:
            await interaction.response.send_message(f"❌ Elemento **{elemento}** não encontrado.", ephemeral=True)
            return
        grupos = {key: organizacao[key]}
    else:
        grupos = organizacao

    # enviar embeds por elemento
    for elem, niveis in grupos.items():
        emoji = emoji_para_elemento(elem)
        embed = discord.Embed(title=f"{emoji} {elem}", color=discord.Color.dark_teal())
        for nivel, lista in niveis.items():
            if lista:
                embed.add_field(name=f"• {nivel} ({len(lista)})", value="\n".join(sorted(lista))[:1024], inline=False)
        await interaction.channel.send(embed=embed)

    await interaction.response.send_message("📜 Listagem enviada.", ephemeral=True)

# ===== Eventos =====
@bot.event
async def on_ready():
    print(f"🚀 Bot conectado como {bot.user}. Sincronizando comandos...")
    try:
        synced = asyncio.run_coroutine_threadsafe(bot.tree.sync(), bot.loop).result(timeout=10)
        print(f"✅ {len(synced)} comandos sincronizados.")
    except Exception as e:
        print("❌ Erro ao sincronizar comandos:", e)

# ===== Execução =====
if __name__ == "__main__":
    # start flask em thread
    threading.Thread(target=run_flask, daemon=True).start()

    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Token não configurado. Configure DISCORD_TOKEN nas env vars.")
    else:
        # roda bot (bloqueante)
        bot.run(TOKEN)
