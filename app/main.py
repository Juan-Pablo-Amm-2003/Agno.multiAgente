# app/main.py
from __future__ import annotations
import os
import re
from typing import List
from urllib.parse import urlparse, urlunparse

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, AnyHttpUrl

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.newspaper4k import Newspaper4kTools

# -----------------------------
# Config
# -----------------------------
def _parse_list(env_val: str | None) -> List[str]:
    return [x.strip() for x in (env_val or "").split(",") if x.strip()]

ALLOWED_ORIGINS = _parse_list(os.getenv("ALLOWED_ORIGINS"))
API_KEY = os.getenv("API_KEY")  # opcional en desarrollo

app = FastAPI(title="editor-team")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or [],  # en prod: lista cerrada
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With", "X-Api-Key"],
)

# -----------------------------
# Seguridad mínima
# -----------------------------
def require_api_key(x_api_key: str | None = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida")
    return True

# -----------------------------
# Pydantic I/O
# -----------------------------
class RunTeamIn(BaseModel):
    topic: str = Field(..., min_length=3, max_length=200)
    max_urls: int = Field(8, ge=1, le=10)

class ArticleSection(BaseModel):
    heading: str
    content: str

class ArticleOut(BaseModel):
    title: str
    summary: str
    body_markdown: str
    sections: List[ArticleSection]
    sources: List[AnyHttpUrl]

class RunTeamOut(BaseModel):
    topic: str
    urls: List[AnyHttpUrl]
    article: ArticleOut

# -----------------------------
# Utils URLs
# -----------------------------
_BAD_HOSTS = {
    "twitter.com","x.com","facebook.com","instagram.com",
    "tiktok.com","reddit.com","linkedin.com","lnkd.in"
}
_SCHEME_RE = re.compile(r"^https?://", re.I)

def _normalize_url(u: str) -> str:
    u = u.strip()
    if not _SCHEME_RE.search(u):
        u = "https://" + u
    parsed = urlparse(u)
    # Normalización simple (sin query para evitar tracking excesivo)
    clean = parsed._replace(fragment="", params="")
    return urlunparse(clean)

def _dedupe_and_filter(raw: List[str], max_n: int) -> List[str]:
    seen, out = set(), []
    for u in raw:
        if not u.strip():
            continue
        if u.lower().endswith(".pdf"):
            continue
        nu = _normalize_url(u)
        host = (urlparse(nu).hostname or "").lower()
        if any(bad in host for bad in _BAD_HOSTS):
            continue
        if nu in seen:
            continue
        seen.add(nu)
        out.append(nu)
        if len(out) >= max_n:
            break
    return out

# -----------------------------
# Agentes
# -----------------------------
searcher = Agent(
    name="Searcher",
    role="Busca y prioriza URLs reputadas.",
    model=OpenAIChat(id="gpt-4o-mini"),  # más barato/rápido
    tools=[DuckDuckGoTools()],
    instructions=[
        "Genera 3 términos de búsqueda enfocados al tema y la región.",
        "Devuelve hasta 10 URLs COMPLETAS, una por línea. Evita PDFs y redes sociales.",
        "No agregues comentarios ni títulos, solo URLs.",
    ],
    add_datetime_to_instructions=True,
    show_tool_calls=True,
    markdown=False,
    request_timeout=60,   # <- importante en cloud
    max_tool_roundtrips=3 # evitar loops largos
)

# Nota: configuramos response_model en el writer para **formato JSON estricto**
writer = Agent(
    name="Writer",
    role="Redacta artículo estilo NYT con fuentes citadas.",
    model=OpenAIChat(id="gpt-4o"),
    tools=[Newspaper4kTools()],
    instructions=[
        "Lee URLs con `read_article`.",
        "Redacta en español rioplatense y tono periodístico; cita explícitamente.",
        "Devuelve la salida usando el esquema provisto (response_model).",
        "Ignora URLs no legibles (PDF/login) sin abortar.",
    ],
    add_datetime_to_instructions=True,
    show_tool_calls=True,
    markdown=True,
    request_timeout=180,
    response_model=ArticleOut,   # <-- clave: salida estructurada Pydantic
    show_full_reasoning=False    # mantener el payload liviano
)

# -----------------------------
# Endpoints
# -----------------------------
@app.get("/health")
def health():
    return {"ok": True, "allowed_origins": ALLOWED_ORIGINS, "has_api_key": bool(API_KEY)}

@app.post("/run-team", response_model=RunTeamOut, dependencies=[Depends(require_api_key)])
def run_team(payload: RunTeamIn):
    topic = payload.topic
    max_urls = payload.max_urls

    # 1) Buscar
    s_prompt = f"Tema: {topic}\nDevuelve solo URLs, una por línea, sin comentarios."
    s_out = searcher.run(s_prompt)
    urls_text = getattr(s_out, "content", str(s_out)) or ""
    raw_urls = [line.strip() for line in urls_text.splitlines()]
    urls = _dedupe_and_filter(raw_urls, max_n=max_urls)
    if not urls:
        raise HTTPException(status_code=502, detail="Searcher no devolvió URLs útiles.")

    # 2) Redactar (con output estructurado)
    w_prompt = (
        f"TEMA: {topic}\n\nFUENTES:\n" + "\n".join(urls) +
        "\n\nDevolvé JSON válido conforme al esquema (title, summary, body_markdown, sections[], sources[])."
    )
    w_out = writer.run(w_prompt)
    article = w_out.content  # ya es ArticleOut por response_model

    return RunTeamOut(topic=topic, urls=urls, article=article)
