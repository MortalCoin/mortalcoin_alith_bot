"""
Signature exchange mechanism for joining games.

This module provides different strategies for exchanging signatures
between player1 and player2 when joining games.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
import aiohttp
import redis
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


@dataclass
class SignatureRequest:
    """Signature request data."""
    game_id: int
    player2_address: str
    signature_expiration: int
    

@dataclass
class SignatureResponse:
    """Signature response data."""
    signature: bytes
    approved: bool
    

class SignatureExchange(ABC):
    """Base class for signature exchange mechanisms."""
    
    @abstractmethod
    async def request_signature(
        self,
        game_id: int,
        player1_address: str,
        player2_address: str,
        signature_expiration: int
    ) -> Optional[bytes]:
        """Request signature from player1 to allow player2 to join."""
        pass
        
    @abstractmethod
    async def provide_signature(
        self,
        request: SignatureRequest,
        private_key: str
    ) -> SignatureResponse:
        """Provide signature for a join request."""
        pass


class RedisSignatureExchange(SignatureExchange):
    """Redis-based signature exchange."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.request_ttl = 300  # 5 minutes
        
    async def request_signature(
        self,
        game_id: int,
        player1_address: str,
        player2_address: str,
        signature_expiration: int
    ) -> Optional[bytes]:
        """Request signature via Redis pub/sub."""
        try:
            # Create request
            request_data = {
                "game_id": game_id,
                "player2_address": player2_address,
                "signature_expiration": signature_expiration,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Store request
            request_key = f"sig_request:{game_id}:{player2_address}"
            self.redis_client.setex(
                request_key,
                self.request_ttl,
                json.dumps(request_data)
            )
            
            # Publish request event
            channel = f"sig_requests:{player1_address}"
            self.redis_client.publish(channel, json.dumps(request_data))
            
            # Wait for response
            response_key = f"sig_response:{game_id}:{player2_address}"
            
            for _ in range(30):  # Wait up to 30 seconds
                response = self.redis_client.get(response_key)
                if response:
                    response_data = json.loads(response)
                    if response_data.get("approved"):
                        return bytes.fromhex(response_data["signature"])
                    else:
                        logger.info("Signature request denied")
                        return None
                        
                await asyncio.sleep(1)
                
            logger.warning("Signature request timed out")
            return None
            
        except Exception as e:
            logger.error(f"Error in Redis signature exchange: {e}")
            return None
            
    async def provide_signature(
        self,
        request: SignatureRequest,
        private_key: str
    ) -> SignatureResponse:
        """Provide signature for a join request."""
        # This would be implemented by the game creator's bot
        # For now, auto-approve for testing
        from web3 import Web3
        from eth_account.messages import encode_structured_data
        
        # Create the structured data for signing
        domain = {
            "name": "MortalCoin",
            "version": "1",
            "chainId": 1,  # Update with actual chain ID
            "verifyingContract": "0x..."  # Update with actual contract address
        }
        
        message = {
            "gameId": request.game_id,
            "player2": request.player2_address,
            "signatureExpiration": request.signature_expiration
        }
        
        types = {
            "JoinGame": [
                {"name": "gameId", "type": "uint256"},
                {"name": "player2", "type": "address"},
                {"name": "signatureExpiration", "type": "uint256"}
            ]
        }
        
        # Sign the message
        account = Web3().eth.account.from_key(private_key)
        signable_message = encode_structured_data({
            "domain": domain,
            "message": message,
            "primaryType": "JoinGame",
            "types": types
        })
        
        signature = account.sign_message(signable_message).signature
        
        return SignatureResponse(
            signature=signature,
            approved=True
        )


class HTTPSignatureExchange(SignatureExchange):
    """HTTP API-based signature exchange."""
    
    def __init__(self, api_url: str):
        self.api_url = api_url
        
    async def request_signature(
        self,
        game_id: int,
        player1_address: str,
        player2_address: str,
        signature_expiration: int
    ) -> Optional[bytes]:
        """Request signature via HTTP API."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/signature/request"
                data = {
                    "game_id": game_id,
                    "player1_address": player1_address,
                    "player2_address": player2_address,
                    "signature_expiration": signature_expiration
                }
                
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("approved"):
                            return bytes.fromhex(result["signature"])
                        else:
                            logger.info("Signature request denied")
                            return None
                    else:
                        logger.error(f"HTTP signature request failed: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error in HTTP signature exchange: {e}")
            return None
            
    async def provide_signature(
        self,
        request: SignatureRequest,
        private_key: str
    ) -> SignatureResponse:
        """Provide signature via HTTP API."""
        # This would be implemented by the signature service
        raise NotImplementedError


class DirectSignatureExchange(SignatureExchange):
    """Direct signature exchange for testing (uses backend key)."""
    
    def __init__(self, backend_private_key: str):
        self.backend_private_key = backend_private_key
        
    async def request_signature(
        self,
        game_id: int,
        player1_address: str,
        player2_address: str,
        signature_expiration: int
    ) -> Optional[bytes]:
        """Generate signature directly (for testing)."""
        logger.warning("Using direct signature exchange - for testing only!")
        
        request = SignatureRequest(
            game_id=game_id,
            player2_address=player2_address,
            signature_expiration=signature_expiration
        )
        
        response = await self.provide_signature(request, self.backend_private_key)
        
        if response.approved:
            return response.signature
        return None
        
    async def provide_signature(
        self,
        request: SignatureRequest,
        private_key: str
    ) -> SignatureResponse:
        """Provide signature directly."""
        from web3 import Web3
        
        # For testing, we'll create a simple signature
        # In production, this should match the contract's expected signature format
        
        web3 = Web3()
        account = web3.eth.account.from_key(private_key)
        
        # Create message hash
        message = web3.solidity_keccak(
            ['uint256', 'address', 'uint256'],
            [request.game_id, request.player2_address, request.signature_expiration]
        )
        
        # Sign the message
        signature = account.signHash(message).signature
        
        return SignatureResponse(
            signature=signature,
            approved=True
        )