from fastapi import FastAPI
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.newspaper4k import Newspaper4kTools

app = FastAPI(title="writer")
agent = Agent(
    name="Writer",
    role="Redacta artículo estilo NYT con fuentes citadas.",
    model=OpenAIChat(id="gpt-4o"),
    tools=[Newspaper4kTools()],
    instructions=[
        "Lee URLs con `read_article`.",
        "Redacta >15 párrafos, con atribuciones, formato Markdown limpio."
    ],
    add_datetime_to_instructions=True,
    show_tool_calls=True,
    markdown=True,
)

@app.post("/run")
async def run(payload: dict):
    topic = payload.get("topic", "")
    urls  = payload.get("urls", [])
    prompt = (
        f"TEMA: {topic}\n\nFUENTES:\n" + "\n".join(urls) +
        "\n\nEntrega pieza estilo NYT, >15 párrafos y lista de fuentes."
    )
    out = agent.run(prompt)
    return {"content": getattr(out, "content", str(out))}
