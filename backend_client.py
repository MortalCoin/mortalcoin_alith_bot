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
        self.refresh_token: Optional[str] = None
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

    async def _refresh_access_token(self) -> bool:
        """Refresh access token using stored refresh token."""
        if not self.refresh_token:
            logger.warning("No refresh token available for access token refresh")
            return False
        await self._ensure_session()
        try:
            url = f"{self.api_url}/api/v1/users/auth/refresh/"
            headers = {"Authorization": f"Bearer {self.refresh_token}"}
            async with self.session.post(url, headers=headers) as response:
                text = await response.text()
                if response.status == 200:
                    data = await response.json()
                    new_access = data.get("access_token")
                    if new_access:
                        self.auth_token = new_access
                        logger.info("\033[92m🔄 Access token refreshed\033[0m")
                        return True
                    logger.error("Refresh response missing access_token")
                    return False
                else:
                    logger.error(f"Failed to refresh access token: {response.status} - {text}")
                    # Invalidate access token to force full re-auth on next call
                    self.auth_token = None
                    return False
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            return False

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        require_auth: bool = True,
        **kwargs
    ) -> tuple[int, str, Optional[Dict[str, Any]]]:
        """Perform an HTTP request with optional auth, auto-refresh and one retry.

        Returns a tuple: (status_code, response_text, json_dict_or_None).
        """
        await self._ensure_session()
        headers = kwargs.pop("headers", {}) or {}
        if require_auth:
            await self._authenticate()
            headers["Authorization"] = f"Bearer {self.auth_token}"

        async with self.session.request(method, url, headers=headers, **kwargs) as response:
            resp_text = await response.text()
            json_data: Optional[Dict[str, Any]] = None
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                try:
                    json_data = await response.json()
                except Exception:
                    json_data = None
            status = response.status

            if status in (401, 403) and require_auth:
                logger.info("Access token may be expired; attempting refresh and retry...")
                if await self._refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.auth_token}"
                    async with self.session.request(method, url, headers=headers, **kwargs) as response2:
                        resp_text2 = await response2.text()
                        json_data2: Optional[Dict[str, Any]] = None
                        content_type2 = response2.headers.get('Content-Type', '')
                        if 'application/json' in content_type2:
                            try:
                                json_data2 = await response2.json()
                            except Exception:
                                json_data2 = None
                        return response2.status, resp_text2, json_data2
            return status, resp_text, json_data
            
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
                    self.refresh_token = result.get("refresh_token")
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
            # Try request; if unauthorized, attempt refresh and retry inside helper
            status, response_text, result = await self._request_with_retry(
                "GET", url, require_auth=True
            )
            logger.info(f"User info API response: {status} - [user data hidden]")
            if status == 200 and isinstance(result, dict):
                self.user_id = str(result.get("id"))
                logger.info(f"\033[94m👤 Got user ID: {self.user_id}\033[0m")
            else:
                logger.error(
                    f"\033[31m❌ Failed to get user info: {status} - {response_text}\033[0m"
                )
                raise Exception(f"Failed to get user info: {status}")
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
            
            status, response_text, result = await self._request_with_retry(
                "POST", url, json=data, require_auth=True
            )
            logger.info(f"\033[96m📤 Add opponent API response: {status} - {response_text}\033[0m")
            if status in (200, 204):
                if status == 200 and isinstance(result, dict):
                    return result
                logger.info(f"\033[92m✅ Successfully added opponent to game {game_id}\033[0m")
                return {"status": "success"}
            else:
                logger.error(f"\033[31m❌ Failed to add opponent: {status} - {response_text}\033[0m")
                return None
                    
        except Exception as e:
            logger.error(f"Error adding opponent: {e}")
            return None
            
    async def get_trading_fight(self, trading_fight_id: str) -> Optional[Dict[str, Any]]:
        """Get trading fight by ID from backend API."""
        await self._ensure_session()
        
        try:
            url = f"{self.api_url}/api/v1/games/trading-fights/{trading_fight_id}/"
            status, response_text, result = await self._request_with_retry(
                "GET", url, require_auth=False
            )
            if status == 200 and isinstance(result, dict):
                return result
            else:
                logger.error(f"Failed to get trading fight: {status} - {response_text}")
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

            status, response_text, result = await self._request_with_retry(
                "POST", url, json=data, require_auth=True
            )
            logger.info(f"Position signature API response: {status} - {response_text}")
            if status == 200 and isinstance(result, dict) and "backend_signature" in result:
                return result
            logger.error("Failed to get position signature (after retry if attempted)")
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
            
            status, response_text, result = await self._request_with_retry(
                "GET", url, params=params, require_auth=True
            )
            logger.info(f"Backend API response: {status} - {response_text}")
            if status == 200:
                if isinstance(result, dict) and "results" in result:
                    return result["results"]
                elif isinstance(result, list):
                    return result
                else:
                    logger.warning(f"Unexpected API response format: {result}")
                    return []
            else:
                logger.error(f"Failed to get available games: {status} - {response_text}")
                return []
                    
        except Exception as e:
            logger.error(f"Error getting available games: {e}")
            return []
            
    async def notify_game_joined(self, game_id: int, tx_hash: str) -> bool:
        """Notify backend that bot joined a game."""
        await self._ensure_session()
        
        try:
            # For now, just log and return success
            logger.info(f"Bot joined game {game_id} with tx {tx_hash}")
            return True
                    
        except Exception as e:
            logger.error(f"Error notifying game joined: {e}")
            return False

    async def start_trading_fight(self, trading_fight_id: str) -> bool:
        """Notify backend to start the trading fight after successful joinGame."""
        await self._authenticate()
        try:
            url = f"{self.api_url}/api/v1/games/trading-fights/{trading_fight_id}/start-fight/"
            status, response_text, _ = await self._request_with_retry(
                "POST", url, require_auth=True
            )
            if status in (200, 204):
                logger.info(f"\033[92m✅ Backend start-fight acknowledged for {trading_fight_id}\033[0m")
                return True
            logger.error(f"\033[31m❌ Failed to start fight: {status} - {response_text}\033[0m")
            return False
        except Exception as e:
            logger.error(f"Error starting trading fight {trading_fight_id}: {e}")
            return False
            
    async def get_price_data(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """Get price data for a pool from backend."""
        await self._ensure_session()
        
        try:
            # Backend might cache price data or provide additional analytics
            url = f"{self.api_url}/api/v1/pools/{pool_address}/price/"
            status, response_text, result = await self._request_with_retry(
                "GET", url, require_auth=False
            )
            if status == 200 and isinstance(result, dict):
                return result
            else:
                logger.debug(f"Failed to get price data from backend: {status} - {response_text}")
                return None
        except Exception as e:
            logger.debug(f"Error getting price data from backend: {e}")
            return None
