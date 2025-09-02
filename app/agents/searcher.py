# app/agents/searcher.py
from fastapi import FastAPI
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools

app = FastAPI(title="searcher")

agent = Agent(
    name="Searcher",
    role="Busca y prioriza URLs reputadas.",
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[DuckDuckGoTools()],
    instructions=[
        "Para el tema, sugiere 3 queries concretas y regionales (ej: agregar país/idioma).",
        "Llama a DuckDuckGo para cada query.",
        "Devuelve SOLO URLs, una por línea. Nada de títulos ni comentarios.",
        "Evita PDFs y redes sociales (Twitter/X, Facebook, Instagram, TikTok, Reddit, LinkedIn).",
        "Cuando dudes entre múltiples resultados, prioriza medios reputados y organismos oficiales.",
    ],
    add_datetime_to_instructions=True,
    show_tool_calls=True,
    markdown=False,
    request_timeout=60,
    max_tool_roundtrips=3
)

@app.post("/run")
def run(payload: dict):
    topic = payload.get("topic", "")
    prompt = f"""Tema: {topic}
STRICT OUTPUT FORMAT:
<solo_urls>
http://...
https://...
</solo_urls>
"""
    out = agent.run(prompt)
    text = getattr(out, "content", str(out)) or ""
    # Defensa extra: si el modelo devolviera tags, los retiramos
    text = text.replace("<solo_urls>", "").replace("</solo_urls>", "").strip()
    return {"content": text}
