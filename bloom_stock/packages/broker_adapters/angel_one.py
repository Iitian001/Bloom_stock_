import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Callable, Optional
import pyotp
from loguru import logger
from SmartApi import SmartConnect, SmartWebSocketV2

from bloom_stock.packages.broker_adapters.base import BrokerAdapter, WebSocketAdapter, AuthSession

class AngelOneWebSocket(WebSocketAdapter):
    """
    WebSocket adapter for Angel One.
    Wraps SmartWebSocketV2.
    """
    def __init__(self, auth_token: str, api_key: str, client_code: str, feed_token: str):
        self.auth_token = auth_token
        self.api_key = api_key
        self.client_code = client_code
        self.feed_token = feed_token
        self.sws = SmartWebSocketV2(auth_token, api_key, client_code, feed_token)
        
        self._on_tick_cb: Optional[Callable] = None
        self._on_connect_cb: Optional[Callable] = None
        self._on_error_cb: Optional[Callable] = None
        self._on_close_cb: Optional[Callable] = None
        
        self._setup_callbacks()

    def _setup_callbacks(self):
        def on_data(wsapp, message):
            if self._on_tick_cb:
                self._on_tick_cb(message)
                
        def on_open(wsapp):
            logger.info("Angel One WebSocket connected.")
            if self._on_connect_cb:
                self._on_connect_cb()
                
        def on_error(wsapp, error):
            logger.error(f"Angel One WebSocket error: {error}")
            if self._on_error_cb:
                self._on_error_cb(error)
                
        def on_close(wsapp):
            logger.info("Angel One WebSocket closed.")
            if self._on_close_cb:
                self._on_close_cb()

        self.sws.on_data = on_data
        self.sws.on_open = on_open
        self.sws.on_error = on_error
        self.sws.on_close = on_close

    async def connect(self) -> None:
        """Connect to the WebSocket in the background."""
        logger.info("Starting Angel One WebSocket connection...")
        # SmartWebSocketV2 blockingly connects. We should ideally run this in a thread or executor.
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.sws.connect)

    async def subscribe(self, tokens: List[str], mode: str) -> None:
        """Subscribe to tokens."""
        # Map modes to Angel One internal values if needed (e.g. 1=LTP, 2=Quote, 3=SnapQuote)
        correlation_id = "stream_1"
        action = 1 # 1 = subscribe
        mode_val = 1 # LTP default for example
        if mode.upper() == "QUOTE": mode_val = 2
        elif mode.upper() == "SNAPQUOTE": mode_val = 3
        
        token_list = [{"exchangeType": 1, "tokens": tokens}] # 1 is NSE for example
        
        logger.info(f"Subscribing to {len(tokens)} tokens with mode {mode}")
        self.sws.subscribe(correlation_id, mode_val, token_list)

    async def unsubscribe(self, tokens: List[str]) -> None:
        """Unsubscribe from tokens."""
        correlation_id = "stream_1"
        action = 0 # 0 = unsubscribe
        mode_val = 1
        token_list = [{"exchangeType": 1, "tokens": tokens}]
        logger.info(f"Unsubscribing from {len(tokens)} tokens")
        self.sws.unsubscribe(correlation_id, mode_val, token_list)

    def on_tick(self, callback: Callable) -> None:
        self._on_tick_cb = callback

    def on_connect(self, callback: Callable) -> None:
        self._on_connect_cb = callback

    def on_error(self, callback: Callable) -> None:
        self._on_error_cb = callback

    def on_close(self, callback: Callable) -> None:
        self._on_close_cb = callback

    async def disconnect(self) -> None:
        """Disconnect WebSocket."""
        logger.info("Disconnecting Angel One WebSocket...")
        self.sws.close_connection()


class AngelOneAdapter(BrokerAdapter):
    """
    BrokerAdapter implementation for Angel One via SmartAPI.
    Implements rate limits, auth rotation, and API interactions.
    """
    def __init__(self, api_key: str, client_id: str, password: str, totp_secret: str, config: Dict[str, Any]):
        self.api_key = api_key
        self.client_id = client_id
        self.password = password
        self.totp_secret = totp_secret
        self.config = config
        
        self.smart_api = SmartConnect(api_key=self.api_key)
        self.session: Optional[AuthSession] = None
        
        # Rate limits from config
        hist_rps = self.config.get("provider", {}).get("historical", {}).get("requests_per_second", 3)
        self._hist_semaphore = asyncio.Semaphore(hist_rps)

    def _generate_totp(self) -> str:
        """Generate TOTP using the secret."""
        return pyotp.TOTP(self.totp_secret).now()

    async def _rate_limit_delay(self):
        """Simple rate limit delay logic. A proper token bucket could be implemented."""
        await asyncio.sleep(0.34) # roughly 3 RPS max

    async def authenticate(self) -> AuthSession:
        """Login and generate tokens."""
        logger.info(f"Authenticating Angel One user: {self.client_id}")
        totp = self._generate_totp()
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            self.smart_api.generateSession,
            self.client_id, self.password, totp
        )
        
        if not response.get('status'):
            logger.error(f"Angel One Auth Failed: {response.get('message')}")
            raise Exception(f"Authentication failed: {response.get('message')}")
            
        data = response['data']
        jwt = data.get('jwtToken')
        feed = data.get('feedToken')
        refresh = data.get('refreshToken')
        
        # Estimate expiration (e.g., 24 hours or end of day)
        expires = datetime.now() + timedelta(hours=24)
        
        self.session = AuthSession(
            jwt_token=jwt,
            feed_token=feed,
            refresh_token=refresh,
            client_id=self.client_id,
            expires_at=expires
        )
        logger.info("Authentication successful.")
        return self.session

    async def refresh_session(self) -> AuthSession:
        """Refresh expired session tokens."""
        if not self.session:
            return await self.authenticate()
            
        logger.info("Refreshing Angel One session...")
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            self.smart_api.renewAccessToken,
            self.session.jwt_token, self.session.refresh_token
        )
        
        if not response.get('status'):
            logger.warning("Session refresh failed, attempting full re-auth.")
            return await self.authenticate()
            
        data = response['data']
        self.session.jwt_token = data.get('jwtToken')
        self.session.refresh_token = data.get('refreshToken')
        self.session.feed_token = data.get('feedToken', self.session.feed_token)
        self.session.expires_at = datetime.now() + timedelta(hours=24)
        
        logger.info("Session refreshed successfully.")
        return self.session

    async def get_instrument_master(self) -> List[Dict[str, Any]]:
        """Download instrument list."""
        logger.info("Downloading instrument master from Angel One...")
        # Note: In a real system, you might fetch this via HTTP directly from Angel's CDN URL.
        # This is a placeholder for the actual request logic.
        return []

    async def get_historical_candles(
        self, 
        symbol_token: str, 
        exchange: str, 
        interval: str, 
        from_dt: datetime, 
        to_dt: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch historical data with rate limiting."""
        async with self._hist_semaphore:
            await self._rate_limit_delay()
            
            params = {
                "exchange": exchange,
                "symboltoken": symbol_token,
                "interval": interval,
                "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"),
                "todate": to_dt.strftime("%Y-%m-%d %H:%M")
            }
            logger.debug(f"Fetching historical data: {params}")
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self.smart_api.getCandleData,
                params
            )
            
            if not response.get('status'):
                logger.error(f"Failed to fetch historical data: {response.get('message')}")
                return []
                
            return response.get('data', [])

    async def place_order(self, order_params: Dict[str, Any]) -> str:
        """Place an order. Returns broker order ID."""
        logger.info(f"Placing order: {order_params}")
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self.smart_api.placeOrder,
            order_params
        )
        if not response.get('status'):
            logger.error(f"Order placement failed: {response.get('message')}")
            raise Exception(f"Order failed: {response.get('message')}")
        return response['data']['orderid']

    async def modify_order(self, order_id: str, params: Dict[str, Any]) -> bool:
        """Modify an existing order."""
        params['orderid'] = order_id
        logger.info(f"Modifying order {order_id}: {params}")
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self.smart_api.modifyOrder,
            params
        )
        return response.get('status', False)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        logger.info(f"Cancelling order {order_id}")
        # Need to provide variety in params depending on API requirements, usually needs variety
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self.smart_api.cancelOrder,
            order_id, "NORMAL" # Assuming variety is NORMAL
        )
        return response.get('status', False)

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get the status of an order."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.smart_api.orderBook)
        if response.get('status'):
            orders = response.get('data', [])
            for o in orders:
                if o.get('orderid') == order_id:
                    return o
        return {}

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.smart_api.position)
        return response.get('data', []) if response.get('status') else []

    async def get_holdings(self) -> List[Dict[str, Any]]:
        """Get current holdings."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.smart_api.holding)
        return response.get('data', []) if response.get('status') else []

    async def get_profile(self) -> Dict[str, Any]:
        """Get user profile details."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.smart_api.getProfile, self.session.refresh_token if self.session else None)
        return response.get('data', {}) if response.get('status') else {}

    def create_websocket_connection(self) -> WebSocketAdapter:
        """Create and return a WebSocket adapter for this broker."""
        if not self.session:
            raise Exception("Cannot create WebSocket connection without authentication.")
            
        return AngelOneWebSocket(
            auth_token=self.session.jwt_token,
            api_key=self.api_key,
            client_code=self.client_id,
            feed_token=self.session.feed_token
        )
