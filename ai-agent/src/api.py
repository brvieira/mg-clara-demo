"""
API HTTP do agente ClaraSeg — expõe src.agent (invoke/astream) via FastAPI.

Único ponto de acoplamento com o resto do backend: assim como a UI Streamlit
(webapp/app.py) só chama agent.invoke(), esta API só chama agent.invoke() e
agent.astream() — nenhuma lógica de grafo/memória/tools vive aqui.

Rodar localmente: uvicorn src.api:app --reload --port 8080 (cwd=ai-agent/)
Rodar em container: ver ai-agent/Dockerfile.
"""
import json
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agent import astream, invoke
from src.config import CORS_ALLOWED_ORIGINS
from src.db import get_db

app = FastAPI(title="ClaraSeg Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    customer_id: str
    message: str
    thread_id: str | None = None


def _new_thread_id(customer_id: str) -> str:
    return f"{customer_id}_{uuid.uuid4().hex[:8]}"


@app.get("/health")
def health():
    """Liveness/readiness check — confirma que o processo responde e que o
    MongoDB (dependência crítica de toda invocação do agente) está acessível."""
    try:
        get_db().command("ping")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB indisponível: {e}")
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    """Chamada não-streaming — equivalente direto de agent.invoke(), para clientes
    que preferem receber a resposta completa de uma vez."""
    thread_id = req.thread_id or _new_thread_id(req.customer_id)
    result = invoke(thread_id, req.customer_id, req.message)
    return {"thread_id": thread_id, **result}


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Chat em streaming via Server-Sent Events. Cada linha `data:` traz um JSON:
      - {"type": "token", "content": str} — pedaço de texto da resposta, na ordem gerada
      - {"type": "done", "response": str, "debug": {...}} — último evento do turno
      - {"type": "error", "detail": str} — em caso de falha

    thread_id é ecoado no primeiro evento (type "start") para que o cliente possa
    persistir a sessão mesmo quando uma nova é criada automaticamente.
    """
    thread_id = req.thread_id or _new_thread_id(req.customer_id)

    async def event_stream():
        yield f"data: {json.dumps({'type': 'start', 'thread_id': thread_id}, ensure_ascii=False)}\n\n"
        async for event in astream(thread_id, req.customer_id, req.message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
