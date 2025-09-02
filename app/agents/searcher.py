from fastapi import FastAPI
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools

app = FastAPI(title="searcher")
agent = Agent(
    name="Searcher",
    role="Busca y prioriza URLs reputadas.",
    model=OpenAIChat(id="gpt-4o"),
    tools=[DuckDuckGoTools()],
    instructions=[
        "Genera 3 términos de búsqueda.",
        "Devuelve hasta 10 URLs reputadas (una por línea). Evita PDFs."
    ],
    add_datetime_to_instructions=True,
    show_tool_calls=True,
    markdown=False,
)

@app.post("/run")
async def run(payload: dict):
    topic = payload.get("topic", "")
    prompt = f"Tema: {topic}\nDevuelve solo URLs, una por línea, sin comentarios."
    out = agent.run(prompt)
    return {"content": getattr(out, "content", str(out))}
