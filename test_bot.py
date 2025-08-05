#!/usr/bin/env python3
"""
Test script for MortalCoin Trading Bot.

This script helps test the bot functionality without running the full bot.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mortalcoin_bot.config import BotConfig
from mortalcoin_bot.backend_client import BackendClient
from mortalcoin_bot.alith_client import AlithClient, MarketData, GameState
from mortalcoin_bot.price_feed import PriceFeedManager
from mortalcoin_bot.blockchain import get_web3_connection, get_contract
from datetime import datetime


async def test_backend_client():
    """Test backend client functionality."""
    print("Testing Backend Client...")
    
    config = BotConfig.from_env()
    backend_client = BackendClient(config.backend_api_url, "0x1234567890123456789012345678901234567890", config.privy_key)
    
    async with backend_client:
        # Test getting available games
        print("\n1. Testing get_available_games...")
        games = await backend_client.get_available_games()
        print(f"Available games: {len(games)}")
        
        # Test getting join signature (will fail without valid game)
        print("\n2. Testing get_join_game_signature...")
        signature = await backend_client.get_join_game_signature(
            game_id=1,
            player1_address="0x1111111111111111111111111111111111111111",
            player2_address="0x2222222222222222222222222222222222222222",
            signature_expiration=1234567890
        )
        print(f"Signature received: {signature is not None}")


async def test_price_feed():
    """Test price feed functionality."""
    print("\nTesting Price Feed...")
    
    config = BotConfig.from_env()
    web3 = get_web3_connection(config.rpc_url)
    contract = get_contract(web3, config.contract_address)
    
    price_feed_manager = PriceFeedManager(web3, contract)
    
    # Test with a dummy pool address
    pool_address = "0x1234567890123456789012345678901234567890"
    
    print(f"\nGetting market data for pool: {pool_address}")
    try:
        market_data = await price_feed_manager.get_market_data(pool_address)
        print(f"Current price: {market_data.current_price}")
        print(f"Price history (last 5): {market_data.price_history[-5:]}")
    except Exception as e:
        print(f"Error getting market data: {e}")


async def test_alith_client():
    """Test Alith AI client functionality."""
    print("\nTesting Alith AI Client...")
    
    config = BotConfig.from_env()
    alith_client = AlithClient(
        openai_api_key=config.openai_api_key,
        model=config.alith_model
    )
    
    # Create test market data
    market_data = MarketData(
        current_price=100.5,
        price_history=[99.8, 100.0, 100.2, 100.3, 100.5],
        timestamp=datetime.now()
    )
    
    # Create test game state
    game_state = GameState(
        game_id=1,
        opponent_address="0x1234567890123456789012345678901234567890",
        opponent_has_position=True,
        opponent_pnl=-0.5,
        my_pnl=1.2,
        time_remaining_seconds=30,
        my_position="long",
        my_position_entry_price=100.0
    )
    
    print("\nGetting trading decision from Alith AI...")
    try:
        decision = alith_client.get_trading_decision(market_data, game_state)
        print(f"Decision: {decision.action}")
        print(f"Reasoning: {decision.reasoning}")
        print(f"Confidence: {decision.confidence}")
    except Exception as e:
        print(f"Error getting decision: {e}")


async def main():
    """Run all tests."""
    print("MortalCoin Trading Bot Test Suite")
    print("=" * 50)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check required environment variables
    required_vars = [
        "MORTALCOIN_RPC_URL",
        "MORTALCOIN_CONTRACT_ADDRESS",
        "MORTALCOIN_BOT_PRIVATE_KEY",
        "OPENAI_API_KEY",
        "MORTALCOIN_BOT_POOL_ADDRESS"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"Missing required environment variables: {missing_vars}")
        print("Please set them in your .env file")
        return
    
    # Run tests
    try:
        await test_backend_client()
    except Exception as e:
        print(f"Backend client test failed: {e}")
    
    try:
        await test_price_feed()
    except Exception as e:
        print(f"Price feed test failed: {e}")
    
    try:
        await test_alith_client()
    except Exception as e:
        print(f"Alith client test failed: {e}")
    
    print("\n" + "=" * 50)
    print("Test suite completed!")


if __name__ == "__main__":
    asyncio.run(main())