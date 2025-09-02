# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.newspaper4k import Newspaper4kTools
import os

app = FastAPI(title="editor-team")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGINS", "*")],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Verificación temprana de credenciales
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("Falta OPENAI_API_KEY en el entorno.")

OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "45"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))

searcher = Agent(
    name="Searcher",
    role="Busca y prioriza URLs reputadas.",
    model=OpenAIChat(
        id="gpt-4o",
        # api_key=os.getenv("OPENAI_API_KEY"),  # opcional; si no, lee del entorno
        request_timeout=OPENAI_TIMEOUT,
        max_retries=OPENAI_MAX_RETRIES,
    ),
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
    model=OpenAIChat(
        id="gpt-4o",
        # api_key=os.getenv("OPENAI_API_KEY"),  # opcional
        request_timeout=OPENAI_TIMEOUT,
        max_retries=OPENAI_MAX_RETRIES,
    ),
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

@app.get("/")
def root():
    return {"ok": True, "service": "editor-team", "docs": "/docs", "health": "/health"}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/run-team")
async def run_team(payload: dict):
    topic = payload.get("topic", "IA generativa en PyMEs LATAM")
    max_urls = int(payload.get("max_urls", 8))

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
