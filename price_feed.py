"""
Price feed integration for Uniswap V2 pools.
"""

import asyncio
import logging
import time
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from web3 import Web3
from web3.contract import Contract

from alith_client import MarketData


logger = logging.getLogger(__name__)


# Uniswap V2 Pair ABI (minimal)
UNISWAP_V2_PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "_reserve0", "type": "uint112"},
            {"name": "_reserve1", "type": "uint112"},
            {"name": "_blockTimestampLast", "type": "uint32"}
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
]


class StableToken:
    """Enum for stable token position in pair."""
    Token0 = 0
    Token1 = 1


class PriceFeed:
    """Base class for price feeds."""
    
    async def get_price(self, pool_address: str) -> float:
        """Get current price for a pool."""
        raise NotImplementedError
        
    async def get_price_history(self, pool_address: str, limit: int = 20) -> List[float]:
        """Get price history for a pool."""
        raise NotImplementedError


class UniswapV2PriceFeed(PriceFeed):
    """Uniswap V2 pool price feed."""
    
    def __init__(self, web3: Web3, contract: Contract, backend_client=None):
        self.web3 = web3
        self.contract = contract  # Main game contract
        self.backend_client = backend_client
        self.pool_contracts: Dict[str, Contract] = {}
        self.price_history: Dict[str, List[Tuple[float, float]]] = {}  # pool -> [(price, timestamp)]
        self.stable_token_cache: Dict[str, int] = {}  # pool -> stable token position
        
    def _get_pool_contract(self, pool_address: str) -> Contract:
        """Get or create pool contract instance."""
        if pool_address not in self.pool_contracts:
            self.pool_contracts[pool_address] = self.web3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=UNISWAP_V2_PAIR_ABI
            )
        return self.pool_contracts[pool_address]
        
    def _get_stable_token(self, pool_address: str) -> int:
        """Get stable token position for pool from contract."""
        if pool_address not in self.stable_token_cache:
            try:
                # Call getPoolStableToken from main contract
                stable_token = self.contract.functions.getPoolStableToken(
                    Web3.to_checksum_address(pool_address)
                ).call()
                self.stable_token_cache[pool_address] = stable_token
            except Exception as e:
                logger.error(f"Error getting stable token for pool {pool_address}: {e}")
                # Default to token0 as stable
                self.stable_token_cache[pool_address] = StableToken.Token0
                
        return self.stable_token_cache[pool_address]
        
    def _calculate_price(self, pool_address: str) -> float:
        """Calculate price based on pool reserves and stable token position."""
        try:
            pool_contract = self._get_pool_contract(pool_address)
            reserves = pool_contract.functions.getReserves().call()
            reserve0 = reserves[0]
            reserve1 = reserves[1]
            
            stable_token = self._get_stable_token(pool_address)
            
            if stable_token == StableToken.Token0:
                # If token0 is stable, divide token0 by token1
                price = (reserve0 * 10**18) / reserve1
            else:
                # If token1 is stable, divide token1 by token0
                price = (reserve1 * 10**18) / reserve0
                
            # Convert to float with 18 decimals precision
            return price / 10**18
            
        except Exception as e:
            logger.error(f"Error calculating price for pool {pool_address}: {e}")
            # Return last known price or default
            if pool_address in self.price_history and self.price_history[pool_address]:
                return self.price_history[pool_address][-1][0]
            return 100.0
            
    async def get_price(self, pool_address: str) -> float:
        """Get current price for a pool."""
        # Try to get from backend first (might have cached/processed data)
        if self.backend_client:
            try:
                price_data = await self.backend_client.get_price_data(pool_address)
                if price_data and "price" in price_data:
                    price = float(price_data["price"])
                    # Store in history
                    if pool_address not in self.price_history:
                        self.price_history[pool_address] = []
                    self.price_history[pool_address].append((price, time.time()))
                    # Keep only last 1000 entries
                    if len(self.price_history[pool_address]) > 1000:
                        self.price_history[pool_address] = self.price_history[pool_address][-1000:]
                    return price
            except Exception as e:
                logger.debug(f"Could not get price from backend: {e}")
                
        # Calculate from pool directly
        price = self._calculate_price(pool_address)
        
        # Store in history
        if pool_address not in self.price_history:
            self.price_history[pool_address] = []
        self.price_history[pool_address].append((price, time.time()))
        
        # Keep only last 1000 entries
        if len(self.price_history[pool_address]) > 1000:
            self.price_history[pool_address] = self.price_history[pool_address][-1000:]
            
        return price
        
    async def get_price_history(self, pool_address: str, limit: int = 20) -> List[float]:
        """Get price history for a pool."""
        # Ensure we have some history
        if pool_address not in self.price_history or not self.price_history[pool_address]:
            # Get current price to start history
            await self.get_price(pool_address)
            
        history = self.price_history.get(pool_address, [])
        
        # Extract just prices (not timestamps)
        prices = [price for price, _ in history]
        
        # If we don't have enough history, pad with the last known price
        if len(prices) < limit:
            last_price = prices[-1] if prices else 100.0
            prices = [last_price] * (limit - len(prices)) + prices
            
        return prices[-limit:]


class PriceFeedManager:
    """Manages price feeds and provides market data."""
    
    def __init__(self, web3: Web3, contract: Contract, backend_client=None):
        self.feed = UniswapV2PriceFeed(web3, contract, backend_client)
        
    async def get_market_data(self, pool_address: str) -> MarketData:
        """Get current market data for a pool."""
        current_price = await self.feed.get_price(pool_address)
        price_history = await self.feed.get_price_history(pool_address)
        
        return MarketData(
            current_price=current_price,
            price_history=price_history,
            timestamp=datetime.now()
        )