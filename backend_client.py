"""
Backend API client for MortalCoin.
"""

import logging
import time
from typing import Optional, Dict, Any
import aiohttp
import asyncio
from web3 import Web3

logger = logging.getLogger(__name__)


class BackendClient:
    """Client for interacting with MortalCoin backend API."""
    
    def __init__(self, api_url: str, bot_address: str, privy_key: str):
        self.api_url = api_url.rstrip('/')
        self.bot_address = bot_address
        self.privy_key = privy_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth_token: Optional[str] = None
        self.user_id: Optional[str] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
    async def _authenticate(self):
        """Authenticate with backend API using Privy key."""
        if self.auth_token is not None:
            return
            
        await self._ensure_session()
        
        try:
            url = f"{self.api_url}/api/v1/users/auth/"
            
            data = {
                "token": self.privy_key
            }
            
            async with self.session.post(url, json=data) as response:
                response_text = await response.text()
                logger.info(f"Auth API response: {response.status} - [token hidden]")
                
                if response.status == 200:
                    result = await response.json()
                    self.auth_token = result.get("access_token")
                    logger.info("\033[92m✅ Successfully authenticated with backend API\033[0m")
                else:
                    logger.error(f"\033[31m❌ Failed to authenticate: {response.status} - {response_text}\033[0m")
                    raise Exception(f"Authentication failed: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            raise
            
    async def _get_user_info(self):
        """Get user information from backend API."""
        if self.user_id is not None:
            return
            
        try:
            url = f"{self.api_url}/api/v1/users/me/"
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            async with self.session.get(url, headers=headers) as response:
                response_text = await response.text()
                logger.info(f"User info API response: {response.status} - [user data hidden]")
                
                if response.status == 200:
                    result = await response.json()
                    self.user_id = str(result.get("id"))
                    logger.info(f"\033[94m👤 Got user ID: {self.user_id}\033[0m")
                else:
                    logger.error(f"\033[31m❌ Failed to get user info: {response.status} - {response_text}\033[0m")
                    raise Exception(f"Failed to get user info: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            raise
            
    async def add_opponent_to_fight(
        self,
        game_id: str,
        player_address: str,
        coin_id: int
    ) -> Optional[Dict[str, Any]]:
        """Add opponent to fight using backend API (like frontend does)."""
        await self._authenticate()
        
        try:
            # Use the endpoint that frontend uses to add opponent to fight
            url = f"{self.api_url}/api/v1/games/trading-fights/{game_id}/add-opponent/"
            
            data = {
                "game_id": game_id,
                "player2": player_address,
                "timestamp": int(time.time()),
                "ttl": 300,  # 5 minutes
                "coin_id": coin_id
            }
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            async with self.session.post(url, json=data, headers=headers) as response:
                response_text = await response.text()
                logger.info(f"\033[96m📤 Add opponent API response: {response.status} - {response_text}\033[0m")
                
                if response.status in [200, 204]:  # 204 = No Content (successful)
                    if response.status == 200:
                        result = await response.json()
                        return result
                    else:
                        # 204 means success but no content
                        logger.info(f"\033[92m✅ Successfully added opponent to game {game_id}\033[0m")
                        return {"status": "success"}
                else:
                    logger.error(f"\033[31m❌ Failed to add opponent: {response.status} - {response_text}\033[0m")
                    return None
                    
        except Exception as e:
            logger.error(f"Error adding opponent: {e}")
            return None
            
    async def get_trading_fight(self, trading_fight_id: str) -> Optional[Dict[str, Any]]:
        """Get trading fight by ID from backend API."""
        await self._ensure_session()
        
        try:
            url = f"{self.api_url}/api/v1/games/trading-fights/{trading_fight_id}/"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    logger.error(f"Failed to get trading fight: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting trading fight: {e}")
            return None
            
    async def get_post_position_signature(
        self,
        game_id: int,
        player_address: str,
        direction: int,
        nonce: int | str,
    ) -> Optional[Dict[str, Any]]:
        """Request backend signature for posting a position using UNHASHED payload.

        Returns the full backend response dict on success, otherwise None. The
        response is expected to include keys: "backend_signature" and
        "signed_message" where signed_message may include "hashedDirection".
        """
        await self._authenticate()

        try:
            url = f"{self.api_url}/api/v1/games/trading-fights/sign-position/"

            data = {
                "gameId": game_id,
                "player": player_address,
                "direction": int(direction),
                # send nonce as string to avoid precision issues in JSON
                "nonce": str(nonce),
            }

            headers = {"Authorization": f"Bearer {self.auth_token}"}

            async with self.session.post(url, json=data, headers=headers) as response:
                response_text = await response.text()
                logger.info(f"Position signature API response: {response.status} - {response_text}")

                if response.status == 200:
                    result = await response.json()
                    # Basic validation
                    if not isinstance(result, dict) or "backend_signature" not in result:
                        logger.error("Unexpected sign-position response format")
                        return None
                    return result
                else:
                    logger.error(
                        f"Failed to get position signature: {response.status} - {response_text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error getting position signature: {e}")
            return None
            
    async def get_available_games(self) -> list[Dict[str, Any]]:
        """Get list of available games to join."""
        await self._authenticate()
        await self._get_user_info()
        
        try:
            # Use the same endpoint as frontend: /api/v1/games/trading-fights/
            # with filters to get available games
            url = f"{self.api_url}/api/v1/games/trading-fights/"
            
            params = {
                "statuses": ["Not started"],  # Only games that haven't started
                "exclude_user_created_fights": "true",  # Don't show our own fights
                "user_id": self.user_id,  # Our user ID for filtering
                "is_creator_online": "true",  # Only games where creator is online
                "limit": 50,  # Get more games
                "offset": 0
            }
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            async with self.session.get(url, params=params, headers=headers) as response:
                response_text = await response.text()
                logger.info(f"Backend API response: {response.status} - {response_text}")
                
                if response.status == 200:
                    result = await response.json()
                    # The API returns a paginated response with results array
                    if isinstance(result, dict) and "results" in result:
                        return result["results"]
                    elif isinstance(result, list):
                        return result
                    else:
                        logger.warning(f"Unexpected API response format: {result}")
                        return []
                else:
                    logger.error(f"Failed to get available games: {response.status} - {response_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting available games: {e}")
            return []
            
    async def notify_game_joined(self, game_id: int, tx_hash: str) -> bool:
        """Notify backend that bot joined a game."""
        await self._ensure_session()
        
        try:
            # For now, we'll skip this notification as it might not be needed
            # The backend might track this automatically through blockchain events
            logger.info(f"Bot joined game {game_id} with tx {tx_hash}")
            return True
                    
        except Exception as e:
            logger.error(f"Error notifying game joined: {e}")
            return False
            
    async def get_price_data(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """Get price data for a pool from backend."""
        await self._ensure_session()
        
        try:
            # Backend might cache price data or provide additional analytics
            url = f"{self.api_url}/api/v1/pools/{pool_address}/price/"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.debug(f"Failed to get price data from backend: {response.status}")
                    return None
                    
        except Exception as e:
            logger.debug(f"Error getting price data from backend: {e}")
            return None
