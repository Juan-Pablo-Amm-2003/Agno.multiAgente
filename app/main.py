from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools
import os
from typing import List

from app.fetcher import fetch_many
from app.db_supabase import log_general, log_error, new_request_id, ping_supabase

app = FastAPI(title="editor-team")

# CORS desde env (o * por defecto en dev)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

searcher = Agent(
    name="Searcher",
    role="Busca y prioriza URLs reputadas.",
    model=OpenAIChat(id=OPENAI_MODEL),
    tools=[DuckDuckGoTools()],
    instructions=[
        "Genera 3 términos de búsqueda.",
        "Devuelve hasta 10 URLs reputadas, una por línea, completas. Evita PDFs y redes sociales.",
    ],
    add_datetime_to_instructions=True,
    show_tool_calls=True,
    markdown=False,
)

# Writer SIN herramientas: trabajará solo con el CORPUS provisto
writer = Agent(
    name="Writer",
    role="Redacta artículo estilo NYT con fuentes citadas.",
    model=OpenAIChat(id=OPENAI_MODEL),
    tools=[],  # <---- importante
    instructions=[
        "Usa EXCLUSIVAMENTE el CORPUS provisto (texto plano extraído de las fuentes).",
        "Redacta en español rioplatense, estilo periodístico (NYT), más de 15 párrafos.",
        "Cita explícitamente las fuentes originales en el texto y agrega una lista final de fuentes.",
        "No inventes datos ni fuentes. Si algo no está en el corpus, no lo afirmes.",
    ],
    add_datetime_to_instructions=True,
    show_tool_calls=False,
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
    return {"ok": True, "supabase": ping_supabase()}


@app.post("/run-team")
async def run_team(payload: RunTeamIn, request: Request):
    req_id = new_request_id()
    topic = payload.topic.strip()
    max_urls = payload.max_urls

    log_general(
        "Inicio de request",
        "/run-team",
        context={"topic": topic, "max_urls": max_urls, "client": request.client.host if request.client else None},
        request_id=req_id,
    )

    try:
        # 1) Buscar URLs
        search_prompt = f"Tema: {topic}\nDevuelve solo URLs, una por línea, sin comentarios."
        s_out = searcher.run(search_prompt)
        urls_text = getattr(s_out, "content", str(s_out))
        urls = [u.strip() for u in urls_text.splitlines() if u.strip().startswith("http")]
        urls = [u for u in urls if not u.lower().endswith(".pdf")][:max_urls]
        if not urls:
            raise HTTPException(status_code=502, detail="Searcher no devolvió URLs útiles.")

        # 2) Extraer texto de las URLs
        results = await fetch_many(urls)
        ok = [r for r in results if r["ok"] and r["text"].strip()]
        failed = [{"url": r["url"], "error": r["error"]} for r in results if not r["ok"]]

        if not ok:
            raise HTTPException(status_code=502, detail="No se pudo acceder a las fuentes seleccionadas.")

        # 3) Construir CORPUS
        MAX_PER_SOURCE = 10_000
        corpus_parts: List[str] = []
        ok_urls: List[str] = []
        for r in ok[:max_urls]:
            corpus_parts.append(f"FUENTE: {r['url']}\n\n{r['text'][:MAX_PER_SOURCE]}")
            ok_urls.append(r["url"])
        corpus = "\n\n-----\n\n".join(corpus_parts)

        # 4) Redactar con CORPUS
        prompt = f"""
TEMA: {topic}

CORPUS (texto plano extraído de las fuentes):
{corpus}

INSTRUCCIONES:
- Redacta en español rioplatense, estilo NYT, más de 15 párrafos.
- Cita explícitamente las fuentes originales con su URL.
- No inventes datos ni fuentes. Usa únicamente el corpus.
- Agrega al final una lista de fuentes (URLs) utilizadas.
""".strip()

        w_out = writer.run(prompt)
        article = getattr(w_out, "content", str(w_out)).strip()
        if not article:
            raise HTTPException(status_code=502, detail="Writer no devolvió artículo.")

        log_general(
            "Artículo generado OK",
            "/run-team",
            context={"topic": topic, "urls": ok_urls, "failed": failed},
            request_id=req_id,
        )

        return {"topic": topic, "urls": ok_urls, "article": article, "failed": failed}

    except HTTPException as e:
        log_error("HTTPException", str(e), "/run-team", context={"topic": topic}, request_id=req_id)
        raise
    except Exception as e:
        log_error("RuntimeError", str(e), "/run-team", context={"topic": topic}, request_id=req_id)
        raise
