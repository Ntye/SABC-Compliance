from __future__ import annotations
import logging
import httpx
from core.errors import ExternalServiceError

logger = logging.getLogger(__name__)


class OllamaClient:
    """HTTP client for a locally-running Ollama inference server.

    Ollama exposes an OpenAI-compatible chat API at POST /api/chat.
    The server must be running on the same host (or reachable LAN address)
    — no internet connection is required once the model is downloaded.

    Resilient model selection
    --------------------------
    The configured model name (OLLAMA_MODEL) is treated as a *preference*,
    not a hard requirement.  If that exact tag is not loaded on the server,
    the client automatically falls back to another available model — first a
    same-family match (e.g. ``llama3.2:1b`` → ``llama3.2:2b``), then any
    loaded model.  This means the chat assistant keeps working regardless of
    which exact tag an operator happened to load, so a model-tag mismatch can
    never silently break the chatbot again.

    Typical setup on the SABC server:
        curl -fsSL https://ollama.com/install.sh | sh   # one-time install
        ollama pull llama3                               # download model
        ollama serve                                     # start server (port 11434)
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self._url = base_url.rstrip("/")
        self._model = model
        # Cache of the model we last successfully resolved to, so we don't
        # re-query /api/tags on every request once a substitute is found.
        self._resolved_model: str | None = None

    @staticmethod
    def _choose(requested: str, available: list[str]) -> str | None:
        """Pick the best available model for a requested tag.

        Preference order: exact match → same family (name before ':') →
        first available.  Returns None when nothing is loaded.
        """
        if not available:
            return None
        if requested in available:
            return requested
        base = requested.split(":")[0]
        for m in available:
            if m.split(":")[0] == base:
                return m
        return available[0]

    async def _post_chat(self, c: httpx.AsyncClient, model: str, messages: list[dict]):
        """POST one chat request. Returns reply text, or None on a 404
        (model-not-found) so the caller can try a substitute."""
        r = await c.post(
            f"{self._url}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")

    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        """Send a chat request and return the assistant's reply text.

        Transparently falls back to an available model if the requested tag
        is not loaded on the server.
        """
        requested = model or self._resolved_model or self._model
        async with httpx.AsyncClient(timeout=120) as c:
            try:
                reply = await self._post_chat(c, requested, messages)
                if reply is not None:
                    self._resolved_model = requested
                    return reply

                # Requested tag isn't loaded — find a substitute and retry.
                available = await self._list_models(c)
                substitute = self._choose(requested, available)
                if substitute is None:
                    raise ExternalServiceError(
                        f"No models are loaded on Ollama at {self._url}. "
                        f"Load one on the server, e.g. ollama pull {requested}."
                    )
                if substitute != requested:
                    logger.warning(
                        "Ollama model '%s' not found; falling back to '%s' "
                        "(loaded: %s)", requested, substitute, ", ".join(available),
                    )
                reply = await self._post_chat(c, substitute, messages)
                if reply is None:
                    raise ExternalServiceError(
                        f"Model '{substitute}' disappeared from Ollama mid-request."
                    )
                self._resolved_model = substitute
                return reply
            except ExternalServiceError:
                raise
            except httpx.ConnectError:
                raise ExternalServiceError(
                    f"Ollama server not reachable at {self._url}. "
                    "Start it with: ollama serve"
                )
            except httpx.HTTPError as e:
                raise ExternalServiceError(f"Ollama API error: {e}") from e

    async def _list_models(self, c: httpx.AsyncClient) -> list[str]:
        try:
            r = await c.get(f"{self._url}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    async def list_models(self) -> list[str]:
        """Return names of locally available models."""
        async with httpx.AsyncClient(timeout=10) as c:
            return await self._list_models(c)

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=5) as c:
            try:
                await c.get(f"{self._url}/")
                return {
                    "status": "up",
                    "url": self._url,
                    "model": self._resolved_model or self._model,
                }
            except Exception:
                return {"status": "not_running", "url": self._url}
