from typing import Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

# --- 1. Connection Manager (連線管理器) ---
class ConnectionManager:
    def __init__(self):
        # 儲存活躍連線: project_id -> List[WebSocket]
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: int):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)
        print(f"Client connected to project {project_id}. Total: {len(self.active_connections[project_id])}")

    def disconnect(self, websocket: WebSocket, project_id: int):
        if project_id in self.active_connections:
            if websocket in self.active_connections[project_id]:
                self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
            print(f"Client disconnected from project {project_id}")

    async def broadcast(self, project_id: int, message: dict):
        """
        廣播訊息給該專案的所有連線者
        message 格式需包含: {"type": str, "sender_id": int, "payload": dict}
        """
        if project_id in self.active_connections:
            # 複製列表避免迭代時修改
            for connection in self.active_connections[project_id][:]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Broadcast error: {e}")
                    # 若發送失敗 (例如連線已斷)，移除該連線
                    self.disconnect(connection, project_id)

# 建立全域管理器實例
manager = ConnectionManager()

# --- 2. WebSocket Router (路由) ---
router = APIRouter()

@router.websocket("/ws/project/{project_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: int, user_id: int):
    await manager.connect(websocket, project_id)
    try:
        while True:
            # 保持連線，這裡可以接收客戶端傳來的訊息 (如果有的話)
            # 目前架構主要是 Server -> Client 廣播，所以這裡只是 blocking 等待
            # 如果未來想做「打字中...」的效果，可以在這裡接收
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)
    except Exception as e:
        print(f"WebSocket Error: {e}")
        manager.disconnect(websocket, project_id)