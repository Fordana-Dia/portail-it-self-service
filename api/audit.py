import json
from datetime import datetime
from fastapi import WebSocket


class ConnectionManager:
    """Gère les connexions WebSocket actives pour le dashboard analyste."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        """Envoie un événement (log ou alerte) à tous les analystes connectés."""
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(data))
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)


manager = ConnectionManager()


async def broadcast_log(user_id: int, username: str, action: str, ressource: str):
    """Diffuse un événement de log d'audit en temps réel."""
    await manager.broadcast({
        "type": "log",
        "user_id": user_id,
        "username": username,
        "action": action,
        "ressource": ressource,
        "timestamp": datetime.utcnow().isoformat()
    })


async def broadcast_alert(severity: str, title: str, message: str, username: str = None):
    """Diffuse une alerte de sécurité en temps réel.

    severity: 'warning' | 'critical'
    """
    await manager.broadcast({
        "type": "alert",
        "severity": severity,
        "title": title,
        "message": message,
        "username": username,
        "timestamp": datetime.utcnow().isoformat()
    })
