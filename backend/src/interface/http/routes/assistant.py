from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/assistant", tags=["Assistant"])

_ollama: object = None  # OllamaClient injected at startup


def set_use_cases(ollama_client):
    global _ollama
    _ollama = ollama_client


_SYSTEM_PROMPT = (
    "You are an expert assistant for the SABC Compliance Platform "
    "(Société Anonyme des Brasseries du Cameroun). "
    "You help system administrators manage Linux servers, CIS benchmark compliance, "
    "Puppet Enterprise node classification, Wazuh SIEM, and InSpec profiles. "
    "Answer in the same language the user writes in (French or English). "
    "Be concise, accurate, and practical."
)


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None


@router.post("/chat", summary="Chat with the offline AI assistant")
async def chat(body: ChatRequest):
    if not _ollama:
        return JSONResponse({"error": "Assistant not configured"}, status_code=503)
    from core.errors import ExternalServiceError
    try:
        msgs = [{"role": "system", "content": _SYSTEM_PROMPT}]
        msgs += [{"role": m.role, "content": m.content} for m in body.messages]
        reply = await _ollama.chat(msgs, model=body.model)
        return {"reply": reply, "model": body.model or _ollama._model}
    except ExternalServiceError as e:
        return JSONResponse({"error": str(e)}, status_code=503)


@router.get("/models", summary="List locally available Ollama models")
async def list_models():
    if not _ollama:
        return {"models": [], "default": None}
    models = await _ollama.list_models()
    return {"models": models, "default": _ollama._model}


@router.get("/health", summary="Check Ollama server health")
async def health():
    if not _ollama:
        return {"status": "not_configured"}
    return await _ollama.health()
