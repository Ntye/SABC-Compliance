from __future__ import annotations
import httpx
from core.errors import ExternalServiceError


class OllamaClient:
    """HTTP client for a locally-running Ollama inference server.

    Ollama exposes an OpenAI-compatible chat API at POST /api/chat.
    The server must be running on the same host (or reachable LAN address)
    — no internet connection is required once the model is downloaded.

    Typical setup on the SABC server:
        curl -fsSL https://ollama.com/install.sh | sh   # one-time install
        ollama pull llama3                               # download model
        ollama serve                                     # start server (port 11434)
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self._url = base_url.rstrip("/")
        self._model = model

    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        """Send a chat request and return the assistant's reply text."""
        model = model or self._model
        async with httpx.AsyncClient(timeout=120) as c:
            try:
                r = await c.post(
                    f"{self._url}/api/chat",
                    json={"model": model, "messages": messages, "stream": False},
                )
                if r.status_code == 404:
                    raise ExternalServiceError(
                        f"Model '{model}' not found on Ollama. "
                        f"Run on the server: ollama pull {model}"
                    )
                r.raise_for_status()
                return r.json().get("message", {}).get("content", "")
            except ExternalServiceError:
                raise
            except httpx.ConnectError:
                raise ExternalServiceError(
                    f"Ollama server not reachable at {self._url}. "
                    "Start it with: ollama serve"
                )
            except httpx.HTTPError as e:
                raise ExternalServiceError(f"Ollama API error: {e}") from e

    async def list_models(self) -> list[str]:
        """Return names of locally available models."""
        async with httpx.AsyncClient(timeout=10) as c:
            try:
                r = await c.get(f"{self._url}/api/tags")
                r.raise_for_status()
                return [m["name"] for m in r.json().get("models", [])]
            except Exception:
                return []

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=5) as c:
            try:
                await c.get(f"{self._url}/")
                return {"status": "up", "url": self._url, "model": self._model}
            except Exception:
                return {"status": "not_running", "url": self._url}
