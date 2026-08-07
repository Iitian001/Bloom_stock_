from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable
from datetime import datetime
from pydantic import BaseModel, Field

class AuthSession(BaseModel):
    """
    Authentication session details.
    """
    jwt_token: str
    feed_token: str
    refresh_token: str
    client_id: str
    expires_at: datetime

class WebSocketAdapter(ABC):
    """
    Abstract Base Class for WebSocket connections to a broker.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to the WebSocket."""
        pass
        
    @abstractmethod
    async def subscribe(self, tokens: List[str], mode: str) -> None:
        """Subscribe to specific instruments."""
        pass
        
    @abstractmethod
    async def unsubscribe(self, tokens: List[str]) -> None:
        """Unsubscribe from specific instruments."""
        pass
        
    @abstractmethod
    def on_tick(self, callback: Callable) -> None:
        """Register a callback for tick data."""
        pass
        
    @abstractmethod
    def on_connect(self, callback: Callable) -> None:
        """Register a callback for when the connection is established."""
        pass
        
    @abstractmethod
    def on_error(self, callback: Callable) -> None:
        """Register a callback for WebSocket errors."""
        pass
        
    @abstractmethod
    def on_close(self, callback: Callable) -> None:
        """Register a callback for when the connection closes."""
        pass
        
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the WebSocket."""
        pass

class BrokerAdapter(ABC):
    """
    Abstract Base Class for broker adapters.
    """
    
    @abstractmethod
    async def authenticate(self) -> AuthSession:
        """Login and get tokens."""
        pass
        
    @abstractmethod
    async def refresh_session(self) -> AuthSession:
        """Refresh expired session."""
        pass
        
    @abstractmethod
    async def get_instrument_master(self) -> List[Dict[str, Any]]:
        """Download instrument list."""
        pass
        
    @abstractmethod
    async def get_historical_candles(
        self, 
        symbol_token: str, 
        exchange: str, 
        interval: str, 
        from_dt: datetime, 
        to_dt: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch historical data."""
        pass
        
    @abstractmethod
    async def place_order(self, order_params: Dict[str, Any]) -> str:
        """Place an order. Returns broker order ID."""
        pass
        
    @abstractmethod
    async def modify_order(self, order_id: str, params: Dict[str, Any]) -> bool:
        """Modify an existing order."""
        pass
        
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        pass
        
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get the status of an order."""
        pass
        
    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        pass
        
    @abstractmethod
    async def get_holdings(self) -> List[Dict[str, Any]]:
        """Get current holdings."""
        pass
        
    @abstractmethod
    async def get_profile(self) -> Dict[str, Any]:
        """Get user profile details."""
        pass
        
    @abstractmethod
    def create_websocket_connection(self) -> WebSocketAdapter:
        """Create and return a WebSocket adapter for this broker."""
        pass
