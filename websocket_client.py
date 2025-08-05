"""
WebSocket client for receiving notifications from MortalCoin backend.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, Callable
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class WebSocketClient:
    """WebSocket client for receiving backend notifications."""
    
    def __init__(self, ws_url: str, auth_token: str):
        self.ws_url = ws_url
        self.auth_token = auth_token
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.running = False
        self.message_handlers: Dict[str, Callable] = {}
        self.message_count = 0  # Counter for incoming messages
        
    async def connect(self):
        """Connect to WebSocket server."""
        try:
            # Connect without any headers (like frontend)
            self.websocket = await websockets.connect(
                self.ws_url
            )
            logger.info(f"\033[92m🔌 Connected to WebSocket at {self.ws_url}\033[0m")
            # Send JWT token as first message for authentication
            auth_message = {"token": self.auth_token}
            logger.info("\033[93m🔐 Sending auth message (token hidden)\033[0m")
            await self.websocket.send(json.dumps(auth_message))
            return True
        except Exception as e:
            logger.error(f"\033[31m❌ Failed to connect to WebSocket: {e}\033[0m")
            return False
            
    async def disconnect(self):
        """Disconnect from WebSocket server."""
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from WebSocket")
            
    def add_message_handler(self, message_type: str, handler: Callable):
        """Add a handler for a specific message type."""
        self.message_handlers[message_type] = handler
        
    async def listen(self):
        """Listen for WebSocket messages."""
        if not self.websocket:
            logger.error("WebSocket not connected")
            return
            
        self.running = True
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse WebSocket message: {e}")
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
        except ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.running = False
            
    async def _handle_message(self, data: Dict[str, Any]):
        """Handle incoming WebSocket message."""
        try:
            self.message_count += 1
            message_type = data.get("type")
            
            # Special handling for signature messages without type
            if not message_type and "signature" in data and "original_request" in data:
                message_type = "signature_ready"
                logger.info(f"\033[95m📨 Received WebSocket message #{self.message_count}: signature_ready (no type field)\033[0m")
            elif not message_type:
                logger.warning(f"\033[33m⚠️  Message without type: {data}\033[0m")
                return
            else:
                logger.info(f"\033[95m📨 Received WebSocket message #{self.message_count}: {message_type}\033[0m")
            
            logger.debug(f"Message data: {data}")
            
            # Call appropriate handler
            if message_type in self.message_handlers:
                await self.message_handlers[message_type](data)
            else:
                logger.info(f"\033[33m⚠️  No handler for message type: {message_type}\033[0m")
                
        except Exception as e:
            logger.error(f"\033[31m❌ Error handling message: {e}\033[0m")
            
    def get_status_info(self) -> str:
        """Get status information for debug logging."""
        # Simple check: if websocket object exists and we connected successfully, assume connected
        if self.websocket and self.running:
            status = "connected"
        else:
            status = "disconnected"
        
        status_emoji = "🟢" if status == "connected" else "🔴"
        return f"\033[95m{status_emoji} WebSocket: {status}, Messages received: {self.message_count}\033[0m"
            
    async def send_message(self, message: Dict[str, Any]):
        """Send a message to the WebSocket server."""
        if not self.websocket:
            logger.error("WebSocket not connected")
            return False
            
        try:
            await self.websocket.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            return False 