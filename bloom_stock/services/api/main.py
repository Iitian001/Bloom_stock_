from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import orjson
from typing import List, Dict, Any

app = FastAPI(title="Bloom_Stock Live Shadow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accepts a WebSocket connection and stores it."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Removes a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Active connections: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcasts a message to all active WebSocket connections."""
        message_bytes = orjson.dumps(message)
        message_str = message_bytes.decode("utf-8")
        
        failed_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"Failed to send message to connection: {e}")
                failed_connections.append(connection)
                
        # Clean up failed connections
        for conn in failed_connections:
            self.disconnect(conn)

manager = ConnectionManager()

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {"status": "ok", "broker_connected": True}

@app.get("/api/v1/risk/status")
async def get_risk_status() -> Dict[str, float]:
    """Retrieves current risk status."""
    # Mock data for now, will connect to real RiskEngine later
    return {
        "daily_drawdown_pct": 0.45,
        "max_leverage_utilization": 2.1,
        "margin_consumption_pct": 45.2
    }

@app.get("/api/v1/regime")
async def get_regime() -> Dict[str, str]:
    """Retrieves current market regime."""
    # Mock data for now
    return {"regime": "TREND_UP"}

@app.websocket("/api/v1/candidates/stream")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming candidate updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Wait for any message from the client to keep the connection alive
            data = await websocket.receive_text()
            logger.debug(f"Received WebSocket message: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}")
        manager.disconnect(websocket)

async def broadcast_candidate(candidate_data: Dict[str, Any]) -> None:
    """Helper function to broadcast new candidates."""
    await manager.broadcast(candidate_data)
