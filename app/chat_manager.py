from fastapi import WebSocket
from typing import Dict, List

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[WebSocket, str]] = {}

    async def connect(self, websocket: WebSocket, group_id: str, username: str):
        await websocket.accept()
        if group_id not in self.active_connections:
            self.active_connections[group_id] = {}
        self.active_connections[group_id][websocket] = username

    def disconnect(self, websocket: WebSocket, group_id: str):
        if group_id in self.active_connections:
            if websocket in self.active_connections[group_id]:
                del self.active_connections[group_id][websocket]
            if not self.active_connections[group_id]:
                del self.active_connections[group_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str, group_id: str, sender: WebSocket = None):
        if group_id in self.active_connections:
            connections = list(self.active_connections[group_id].keys())
            for connection in connections:
                if connection != sender:
                    try:
                        await connection.send_text(message)
                    except Exception:
                        pass

    def get_members(self, group_id: str) -> List[str]:
        if group_id in self.active_connections:
            return list(set(self.active_connections[group_id].values()))
        return []

manager = ConnectionManager()
