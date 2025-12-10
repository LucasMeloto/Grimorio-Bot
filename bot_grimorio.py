# bot.py — Grimório FINAL (versão F, modo 3)
# Requisitos: python3.8+, pip install discord.py flask requests

import discord
from discord import app_commands
from discord.ext import commands
import json
import re
import os
import threading
import time
from typing import List, Tuple, Optional

# requests é usado para tentar resolver páginas (Tenor / og:image)
try:
    import requests
except Exception:
    requests = None  # fallback; se não tiver, o bot ainda funciona sem resolução extra

# -------------------------
# Keepalive (opcional)
# -------------------------
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "🪄 Grimório ativo!"

def run_flask():
    # Em produção use WSGI; use_reloader=False evita duplicar threads
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), use_reloader=False)

# -------------------------
# Configurações
# -------------------------
MAX_IMAGES_SEND = 8  # envia até N imagens por magia (ajuste aqui)

ELEMENT_ICONS = {
    "fogo":"🔥","fire":"🔥",
    "água":"💧","agua":"💧","water":"💧",
    "terra":"🌱","earth":"🌱",
    "ar":"🌬️","vento":"🌬️","wind":"🌬️",
    "raio":"⚡","lightning":"⚡","electric":"⚡",
    "luz":"☀️","light":"☀️",
    "escuridão":"🌑","escuro":"🌑","dark":"🌑",
    "arcano":"🔮","dimensional":"🌀","tempo":"⌛","status":"💠",
    "unknown":"❔"
}

ELEMENTOS_VALIDOS = set([
    "fogo","fire","água","agua","water",
    "terra","earth","ar","vento","wind",
    "raio","lightning","electric",
    "luz","light","escuridão","dark",
    "arcano","dimensional","tempo","status","neutro","neutral"
])

# -------------------------
# Utilitários de texto / html
# -------------------------
def clean_str(s: Optional[str]) -> str:
    if not s:
        return ""
    t = str(s).strip()
    t = re.sub(r"^[^\wáéíóúãõâêôç]+", "", t)
    t = re.sub(r"[^\w\sáéíóúãõâêôç\-]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.lower()

def normalize_query(q: Optional[str]) -> str:
    if not q:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(q).lower())

def get_element_icon(raw: Optional[str]) -> Tuple[str,str]:
    raw = raw or ""
    clean = clean_str(raw)
    if clean in ELEMENT_ICONS:
        return clean, ELEMENT_ICONS[clean]
    first = clean.split()[0] if clean else ""
    if first in ELEMENT_ICONS:
        return clean, ELEMENT_ICONS[first]
    # try capture emoji from raw start
    m = re.match(r"^([^\w\s]+)", raw.strip()) if raw.strip() else None
    if m:
        return clean, m.group(1)
    return clean, "❔"

def strip_html_basic(text: str) -> str:
    if not text:
        return ""
    t = str(text)
    t = t.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    t = re.sub(r"</?(p|div|span|strong|em|b|i|u)[^>]*>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<img[^>]*>", "", t, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\r\n?", "\n", t)
    t = re.sub(r"\n{2,}", "\n\n", t)
    return t.strip()

# -------------------------
# Resolver links (Tenor/og:image)
# - tenta pegar og:image ou primeira <meta property="og:image" content="...">
# - requer 'requests' instalado; se não, apenas retorna a url original
# -------------------------
def try_resolve_media(url: str, timeout: float = 3.0) -> str:
    """
    Tenta retornar um URL direto de imagem para o url fornecido.
    Se não conseguir, retorna o url original.
    """
    if not url:
        return url
    # quick heuristic: if url already ends with image ext, return it
    if re.search(r"\.(gif|png|jpg|jpeg|webp|mp4|webm)(?:\?.*)?$", url, flags=re.IGNORECASE):
        return url

    # if requests unavailable, give up
    if not requests:
        return url

    try:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) GrimorioBot/1.0"}
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            return url
        html = r.text

        # try og:image
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if candidate:
                return candidate

        # try twitter image meta
        m2 = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        if m2:
            return m2.group(1).strip()

        # try first <img src="">
        m3 = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        if m3:
            return m3.group(1).strip()

        return url
    except Exception:
        return url

# -------------------------
# Extrator: imagens + campos (Efeito multiline, limitações multilinha, notas)
# -------------------------
def extract_images_and_fields(desc_raw: str):
    """
    Retorna:
      desc_base (str),
      efeito (str),
      custo (str),
      cooldown (str),
      duracao (str),
      lista_lim (list[str]),
      notas (str),
      imagens_resolvidas (list[str])
    """
    if not desc_raw:
        return "", "", "", "", "", [], "", []

    s = str(desc_raw)

    # 1) coletar imagens / gifs (preservando ordem)
    imgs = []
    seen = set()
    for m in re.finditer(r'<img[^>]*src=["\']([^"\']+)["\']', s, flags=re.IGNORECASE):
        url = m.group(1).strip()
        if url and url not in seen:
            imgs.append(url); seen.add(url)
    for m in re.finditer(r'(https?://[^\s\'"<>]+\.(?:gif|png|jpg|jpeg|webp|mp4|webm))', s, flags=re.IGNORECASE):
        url = m.group(1).strip()
        if url and url not in seen:
            imgs.append(url); seen.add(url)

    # 2) limpar html para texto
    clean = strip_html_basic(s)

    # 3) extrair efeito bloco multiline (captura até próximo label)
    # labels que terminam o bloco de efeito
    end_labels = r'(?:\n(?:Custo|Mana|Cost|Cooldown|CD|Dura(?:ç|c)ao|Duracao|Duration|Limita(?:ç|c)[oõ]es|Limitacoes|Restricoes|Restrições)\s*:)'
    m_eff = re.search(r'(?:^|\n)(?:Efeito|Effect)\s*:\s*(.+?)(?=' + end_labels + r'|$)', clean, flags=re.IGNORECASE | re.DOTALL)
    efeito = m_eff.group(1).strip() if m_eff else ""

    # 4) campos single-line tolerantes
    def single(labels):
        for L in labels:
            m = re.search(rf'(?:^|\n){re.escape(L)}\s*:\s*(.+?)(?:\n|$)', clean, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""
    custo = single(["Custo","Mana","Cost","Custo de mana"])
    cooldown = single(["Cooldown","CD"])
    duracao = single(["Duração","Duracao","Duration"])

    # 5) limitações multilinha (captura bloco inteiro)
    lista_lim = []
    m_lim = re.search(
        r'(?:^|\n)(?:Limitações|Limitacoes|Limita(?:ç|c)[oõ]es|Restrições|Restricoes)\s*:\s*(.+?)(?=\n(?:Custo|Cooldown|Dura|Efeito|Notas|$)|$)',
        clean,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m_lim:
        bloco = m_lim.group(1).strip()
        partes = re.split(r'[\n•\-]', bloco)
        for p in partes:
            ln = p.strip(" .:•\t\r")
            if ln:
                lista_lim.append(ln)

    # 6) descrição base (antes de Efeito:)
    parts = re.split(r'(?:^|\n)(?:Efeito|Effect)\s*:', clean, flags=re.IGNORECASE)
    desc_base = parts[0].strip() if parts else clean

    # 7) notas/extras: rest of text after removing captured blocks
    temp = clean
    if m_eff:
        temp = temp.replace(m_eff.group(0), "")
    if m_lim:
        temp = temp.replace(m_lim.group(0), "")
    # remove single fields lines
    for lab in ["Custo","Mana","Cost","Cooldown","CD","Duração","Duracao","Duration","Limitações","Limitacoes","Restrições","Restricoes"]:
        temp = re.sub(rf'(?:^|\n){lab}\s*:\s*.+?(?:\n|$)', '\n', temp, flags=re.IGNORECASE)
    # remove desc_base once
    if desc_base:
        temp = temp.replace(desc_base, "", 1)
    notas = temp.strip()
    notas = re.sub(r'\n{2,}', '\n\n', notas).strip()

    # 8) tentar resolver imagens (og:image) para domínios como tenor/twitter/etc (com requests)
    resolved = []
    for url in imgs:
        try:
            resolved_url = try_resolve_media(url)
            resolved.append(resolved_url)
        except Exception:
            resolved.append(url)
    # keep order, unique
    final_imgs = []
    seen2 = set()
    for u in resolved:
        if u and u not in seen2:
            final_imgs.append(u); seen2.add(u)

    return desc_base, efeito, custo, cooldown, duracao, lista_lim, notas, final_imgs

# -------------------------
# Carregar JSON (compatível com blocos)
# -------------------------
JSON_FILE = "grimorio_completo.json"
MAGIAS = []

def load_spells(path=JSON_FILE):
    global MAGIAS
    MAGIAS = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("❌ Erro ao abrir JSON:", e)
        return

    def normalize(m):
        title = m.get("title") or m.get("titulo") or m.get("name") or m.get("nome") or "Sem título"
        raw_elem = m.get("element") or m.get("elemento") or m.get("tipo") or ""
        elem_clean, icon = get_element_icon(raw_elem)
        desc = m.get("description") or m.get("descricao") or m.get("desc") or ""
        cats = m.get("categories") or m.get("categorias") or m.get("tags") or []
        cats_norm = [clean_str(x).capitalize() for x in cats] if cats else []
        # explicit limitations if present in object
        explicit_limits = []
        for k in ("limitations","limitacoes","limitações","restricoes","restrições"):
            if k in m and m[k]:
                v = m[k]
                if isinstance(v, list):
                    explicit_limits.extend([str(x).strip() for x in v if str(x).strip()])
                else:
                    explicit_limits.append(str(v).strip())
        return {
            "title": title,
            "element_raw": raw_elem,
            "element": elem_clean,
            "icon": icon,
            "description": desc,
            "categories": cats_norm,
            "explicit_limits": explicit_limits,
            "_orig": m
        }

    if isinstance(data, list) and data and isinstance(data[0], dict) and "magias" in data[0]:
        for bloco in data:
            bloco_elem = bloco.get("element") or bloco.get("elemento") or ""
            for m in bloco.get("magias", []):
                if not m.get("element"):
                    m["element"] = bloco_elem
                MAGIAS.append(normalize(m))
    else:
        if isinstance(data, list):
            for m in data:
                if isinstance(m, dict):
                    MAGIAS.append(normalize(m))
    print(f"✅ Magias carregadas: {len(MAGIAS)}")

# load at start
load_spells()

# -------------------------
# Bot setup
# -------------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.synced = False

# per-user debounce (to reduce spam)
user_search_ts = {}

# Autocomplete
async def autocomplete_magias(interaction: discord.Interaction, current: str):
    norm = normalize_query(current)
    choices = []
    for m in MAGIAS:
        if norm in normalize_query(m["title"]):
            choices.append(app_commands.Choice(name=m["title"][:100], value=m["title"]))
        if len(choices) >= 25:
            break
    return choices

# -------------------------
# /magia (defer + followups) — mostra tudo e envia imagens extras
# -------------------------
@bot.tree.command(name="magia", description="Consulta detalhes de uma magia.")
@app_commands.autocomplete(nome=autocomplete_magias)
async def cmd_magia(interaction: discord.Interaction, nome: str):
    await interaction.response.defer()
    alvo = None
    norm = normalize_query(nome)
    for m in MAGIAS:
        if normalize_query(m["title"]) == norm:
            alvo = m; break
    if not alvo:
        return await interaction.followup.send(f"❌ Magia **{nome}** não encontrada.", ephemeral=True)

    desc_raw = alvo["description"] or ""
    desc_base, efeito, custo, cooldown, duracao, lista_lim, notas, imagens = extract_images_and_fields(desc_raw)

    # juntar limitações explícitas + extraídas
    limits = []
    if isinstance(alvo.get("explicit_limits"), list):
        limits.extend([x for x in alvo["explicit_limits"] if x])
    if lista_lim:
        limits.extend([x for x in lista_lim if x])
    # check original object keys as fallback
    orig = alvo.get("_orig", {})
    for k in ("limitações","limitacoes","limitations","restricoes","restrições"):
        v = orig.get(k)
        if v:
            if isinstance(v, list):
                limits.extend([str(x).strip() for x in v if str(x).strip()])
            else:
                limits.append(str(v).strip())
    # dedupe preserving order
    final_limits = []
    seen_l = set()
    for it in limits:
        if it and it not in seen_l:
            final_limits.append(it); seen_l.add(it)

    titulo = alvo["title"]
    icon = alvo["icon"] or "❔"
    elemento = alvo["element"].capitalize() if alvo["element"] else clean_str(alvo["element_raw"]).capitalize() or "Desconhecido"
    cats = ", ".join(alvo["categories"]) if alvo["categories"] else "Nenhuma"

    def trunc(t, lim=1024):
        if not t:
            return ""
        t = str(t)
        return t if len(t) <= lim else t[:lim-3] + "..."

    embed = discord.Embed(title=f"{icon} {titulo}", description=trunc(desc_base) or "Sem descrição.", color=discord.Color.orange())
    embed.add_field(name="🎯 Efeito", value=trunc(efeito) or "Não informado.", inline=False)
    if notas:
        embed.add_field(name="📝 Notas / Extras", value=trunc(notas), inline=False)
    embed.add_field(name="💧 Custo", value=custo or "?", inline=True)
    embed.add_field(name="⏳ Cooldown", value=cooldown or "?", inline=True)
    embed.add_field(name="⌛ Duração", value=duracao or "?", inline=True)
    embed.add_field(name="⚠️ Limitações", value="\n".join(f"• {l}" for l in final_limits) if final_limits else "Nenhuma.", inline=False)
    embed.set_footer(text=f"Categorias: {cats} — Elemento: {elemento}")

    # set first image if available and is valid
    if imagens:
        # limit images count
        imagens = imagens[:MAX_IMAGES_SEND]
        first = imagens[0]
        try:
            await interaction.followup.send(embed=embed, wait=True)  # send embed first as followup
        except Exception:
            # fallback: send embed via response if followup fails
            await interaction.followup.send(embed=embed)
        # enviar imagens extras: for each image send an embed with image
        for img in imagens:
            try:
                resolved = try_resolve_media(img) if requests else img
                if resolved and len(resolved) > 0:
                    e = discord.Embed(color=discord.Color.orange())
                    e.set_image(url=resolved)
                    await interaction.followup.send(embed=e)
            except Exception:
                continue
    else:
        # no images: just send embed
        await interaction.followup.send(embed=embed)

# -------------------------
# Inteligent /buscar (modo 3)
# - if query is element -> search element + categories + title
# - else -> search title + categories + description
# -------------------------
@bot.tree.command(name="buscar", description="Busca magias por nome, elemento, categoria ou descrição.")
@app_commands.describe(term="Elemento (fogo) ou palavra (teleporte)")
async def cmd_buscar(interaction: discord.Interaction, term: str):
    user = interaction.user.id
    now = time.time()
    last = user_search_ts.get(user, 0)
    if now - last < 0.7:
        return await interaction.response.send_message("⏳ Aguarde 1s entre buscas.", ephemeral=True)
    user_search_ts[user] = now

    norm = normalize_query(term)
    results = []

    if norm in ELEMENTOS_VALIDOS:
        # strict element search
        for m in MAGIAS:
            if norm == m["element"]:
                results.append(m["title"]); continue
            if norm in normalize_query(" ".join(m["categories"])):
                results.append(m["title"]); continue
            if norm in normalize_query(m["title"]):
                results.append(m["title"]); continue
    else:
        # broad search
        for m in MAGIAS:
            if (norm in normalize_query(m["title"])
                or norm in normalize_query(" ".join(m["categories"]))
                or norm in normalize_query(m["description"])):
                results.append(m["title"])

    if not results:
        return await interaction.response.send_message(f"❌ Nenhuma magia encontrada para **{term}**.", ephemeral=True)

    # dedupe + sort
    uniq = sorted(set(results))
    text = "\n".join(f"• {t}" for t in uniq)
    if len(text) > 4000:
        text = text[:3990] + "\n... (truncado)"

    embed = discord.Embed(title=f"🔍 Resultados ({len(uniq)})", description=text, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

# -------------------------
# /listar (elemento / categoria / todas)
# -------------------------
@bot.tree.command(name="listar", description="Lista magias por elemento, categoria ou todas.")
@app_commands.describe(filtro="Ex: fogo, água, suprema, todas")
async def cmd_listar(interaction: discord.Interaction, filtro: str):
    norm = normalize_query(filtro)
    results = []
    for m in MAGIAS:
        if norm == "todas":
            results.append(m["title"]); continue
        if norm == m["element"]:
            results.append(m["title"]); continue
        if norm in normalize_query(" ".join(m["categories"])):
            results.append(m["title"]); continue

    if not results:
        return await interaction.response.send_message(f"❌ Nada encontrado para **{filtro}**.", ephemeral=True)

    text = "\n".join(f"• {t}" for t in sorted(set(results)))
    if len(text) > 4000:
        text = text[:3990] + "\n... (truncado)"
    embed = discord.Embed(title=f"📘 Lista ({len(results)}) — {filtro.capitalize()}", description=text, color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

# -------------------------
# /reload — recarrega JSON em runtime (owner/manage_guild)
# -------------------------
@bot.tree.command(name="reload", description="Recarrega o arquivo grimorio_completo.json (admin/dono).")
async def cmd_reload(interaction: discord.Interaction):
    is_owner = await bot.is_owner(interaction.user)
    has_perm = False
    try:
        if interaction.guild:
            member = interaction.guild.get_member(interaction.user.id)
            if member and (member.guild_permissions.manage_guild or member.guild_permissions.administrator):
                has_perm = True
    except Exception:
        pass
    if not (is_owner or has_perm):
        return await interaction.response.send_message("❌ Você não tem permissão para usar /reload.", ephemeral=True)

    load_spells()
    return await interaction.response.send_message("✅ Grimório recarregado.", ephemeral=True)

# -------------------------
# on_ready (sync once)
# -------------------------
@bot.event
async def on_ready():
    print(f"🤖 Conectado como {bot.user} (id={bot.user.id})")
    if not getattr(bot, "synced", False):
        try:
            await bot.tree.sync()
            bot.synced = True
            print("✨ Comandos sincronizados.")
        except Exception as e:
            print("❌ Erro ao sincronizar comandos:", e)

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    # start keepalive (optional)
    threading.Thread(target=run_flask, daemon=True).start()

    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Defina DISCORD_TOKEN nas variáveis de ambiente.")
    else:
        bot.run(TOKEN)
