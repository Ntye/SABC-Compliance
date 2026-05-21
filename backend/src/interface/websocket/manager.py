from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self, job_repository=None) -> None:
        self._clients: dict[str, set] = {}
        self._job_repo = job_repository

    async def connect(self, job_id: str, websocket) -> None:
        await websocket.accept()
        # Replay stored logs to the newly connected client
        if self._job_repo:
            job = await self._job_repo.find_by_id(job_id)
            if job:
                for entry in job.logs:
                    try:
                        await websocket.send_json(entry)
                    except Exception:
                        return
        self._clients.setdefault(job_id, set()).add(websocket)

    def disconnect(self, job_id: str, websocket) -> None:
        if job_id in self._clients:
            self._clients[job_id].discard(websocket)

    async def broadcast(self, job_id: str, message: dict) -> None:
        dead: set = set()
        for ws in list(self._clients.get(job_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        if dead and job_id in self._clients:
            self._clients[job_id] -= dead

    async def broadcast_node(self, node_id: str, message: dict) -> None:
        await self.broadcast(f"node-{node_id}", message)
