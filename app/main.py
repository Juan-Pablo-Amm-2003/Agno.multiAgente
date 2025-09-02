# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.newspaper4k import Newspaper4kTools
import os

app = FastAPI(title="editor-team")

# CORS desde env (o * por defecto en dev)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # opcional por env

searcher = Agent(
    name="Searcher",
    role="Busca y prioriza URLs reputadas.",
    model=OpenAIChat(id=OPENAI_MODEL),   # <-- sin request_timeout / max_retries / client
    tools=[DuckDuckGoTools()],
    instructions=[
        "Genera 3 términos de búsqueda.",
        "Devuelve hasta 10 URLs reputadas, una por línea, completas. Evita PDFs y redes sociales.",
    ],
    add_datetime_to_instructions=True,
    show_tool_calls=True,
    markdown=False,
)

writer = Agent(
    name="Writer",
    role="Redacta artículo estilo NYT con fuentes citadas.",
    model=OpenAIChat(id=OPENAI_MODEL),   # <-- igual aquí
    tools=[Newspaper4kTools()],
    instructions=[
        "Lee URLs con `read_article`.",
        "Redacta en español rioplatense, >15 párrafos, con atribuciones y lista de fuentes.",
        "Ignora URLs no legibles (PDF/login) sin bloquear la redacción.",
    ],
    add_datetime_to_instructions=True,
    show_tool_calls=True,
    markdown=True,
)

class RunTeamIn(BaseModel):
    topic: str = Field(default="IA generativa en PyMEs LATAM", min_length=3)
    max_urls: int = Field(default=8, ge=1, le=12)

@app.get("/")
def root():
    return {"service": "editor-team", "docs": "/docs", "health": "/health"}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/run-team")
async def run_team(payload: RunTeamIn):
    topic = payload.topic
    max_urls = payload.max_urls

    # 1) Buscar URLs
    search_prompt = f"Tema: {topic}\nDevuelve solo URLs, una por línea, sin comentarios."
    s_out = searcher.run(search_prompt)
    urls_text = getattr(s_out, "content", str(s_out))
    urls = [u.strip() for u in urls_text.splitlines() if u.startswith("http")]
    urls = [u for u in urls if not u.lower().endswith(".pdf")][:max_urls]
    if not urls:
        raise HTTPException(status_code=502, detail="Searcher no devolvió URLs útiles.")

    # 2) Redactar
    prompt = (
        f"TEMA: {topic}\n\nFUENTES:\n" + "\n".join(urls) +
        "\n\nEntrega pieza estilo NYT, >15 párrafos y lista de fuentes."
    )
    w_out = writer.run(prompt)
    article = getattr(w_out, "content", str(w_out))
    if not article:
        raise HTTPException(status_code=502, detail="Writer no devolvió artículo.")

    return {"topic": topic, "urls": urls, "article": article}
