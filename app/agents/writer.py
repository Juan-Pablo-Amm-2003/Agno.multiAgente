# app/agents/writer.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, AnyHttpUrl
from typing import List

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.newspaper4k import Newspaper4kTools

class ArticleSection(BaseModel):
    heading: str
    content: str

class ArticleOut(BaseModel):
    title: str
    summary: str
    body_markdown: str
    sections: List[ArticleSection]
    sources: List[AnyHttpUrl]

app = FastAPI(title="writer")

agent = Agent(
    name="Writer",
    role="Redacta artículo estilo NYT con fuentes citadas.",
    model=OpenAIChat(id="gpt-4o"),
    tools=[Newspaper4kTools()],
    instructions=[
        "Lee cada URL con `read_article`. Si alguna falla (PDF/login/timeout), sáltala y continúa.",
        "Escribe en español rioplatense; 15+ párrafos. Usa citas y atribuciones con medios/fuentes.",
        "Devuelve salida ESTRICTAMENTE conforme al esquema (response_model).",
        "Separa contenido en secciones lógicas (contexto, impacto, riesgos, recomendaciones).",
        "Incluye la lista final de sources[] con URLs válidas.",
    ],
    add_datetime_to_instructions=True,
    show_tool_calls=True,
    markdown=True,
    request_timeout=180,
    response_model=ArticleOut,
)

@app.post("/run")
def run(payload: dict):
    topic = payload.get("topic", "").strip()
    urls  = payload.get("urls", [])
    if not topic or not urls:
        raise HTTPException(status_code=422, detail="Faltan 'topic' o 'urls'")

    prompt = (
        f"TEMA: {topic}\n\nFUENTES:\n" + "\n".join(urls) +
        "\n\nEntregá JSON válido con title, summary, body_markdown, sections[], sources[]."
    )
    out = agent.run(prompt)
    return {"content": out.content}  # ya es ArticleOut
