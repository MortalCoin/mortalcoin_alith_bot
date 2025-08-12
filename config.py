"""
Configuration settings for MortalCoin Trading Bot.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BotConfig:
    """Bot configuration settings."""
    
    # Blockchain settings
    rpc_url: str
    contract_address: str
    bot_private_key: str
    
    # AI settings
    openai_api_key: str
    
    # Authentication settings
    # Legacy Privy auth token (optional if headless auth is used)
    privy_key: Optional[str] = None
    # Headless auth controls
    use_headless_auth: bool = True
    headless_message: str = "Login MortalCoin headless"
    privy_user_id: Optional[str] = None
    
    # Pool settings
    bot_pool_address: str
    
    # Backend API settings
    backend_api_url: str = "https://testapi.mortalcoin.app"
    
    # AI settings
    alith_model: str = "gpt-4"
    
    # Trading settings
    bet_amount_eth: float = 0.0001
    
    # Game settings
    position_hold_time_max: int = 50  # Maximum time to hold a position in seconds (game is 60s)
    game_duration_seconds: int = 60  # Fixed game duration
    
    # Monitoring settings
    monitor_interval_seconds: int = 5
    
    # Game joining settings
    game_search_interval_seconds: int = 10  # How often to search for available games to join
    
    # Pool settings
    pool_coin_id: int = 1  # Coin ID for the pool, getting from frontend (1 for BTC)
    
    # Database settings
    db_path: str = "mortalcoin_bot.db"
    
    @classmethod
    def from_env(cls) -> "BotConfig":
        """Create config from environment variables."""
        # Normalize private key to ensure it has 0x prefix
        private_key = os.environ["MORTALCOIN_BOT_PRIVATE_KEY"]
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
            
        # Determine auth mode
        headless_flag = os.getenv("MORTALCOIN_HEADLESS_AUTH", "1").strip().lower()
        use_headless_auth = headless_flag in ("1", "true", "yes", "on")

        # Optional Privy key for legacy flow or mapping
        privy_key = os.getenv("MORTALCOIN_PRIVY_KEY")

        # Optional Privy user id required by backend for headless mapping/creation
        privy_user_id = os.getenv("MORTALCOIN_PRIVY_USER_ID")

        # Fixed expected message if backend enforces it; otherwise default used
        headless_message = os.getenv("MORTALCOIN_HEADLESS_MESSAGE", "Login MortalCoin headless")

        return cls(
            rpc_url=os.environ["MORTALCOIN_RPC_URL"],
            contract_address=os.environ["MORTALCOIN_CONTRACT_ADDRESS"],
            bot_private_key=private_key,
            backend_api_url=os.getenv("MORTALCOIN_BACKEND_API_URL", "https://testapi.mortalcoin.app"),
            alith_model=os.getenv("ALITH_MODEL", "gpt-4"),
            openai_api_key=os.environ["OPENAI_API_KEY"],
            privy_key=privy_key,
            use_headless_auth=use_headless_auth,
            headless_message=headless_message,
            privy_user_id=privy_user_id,
            bet_amount_eth=float(os.getenv("MORTALCOIN_BET_AMOUNT", "0.0001")),
            bot_pool_address=os.environ["MORTALCOIN_BOT_POOL_ADDRESS"],

            position_hold_time_max=int(os.getenv("MORTALCOIN_POSITION_HOLD_MAX", "50")),
            game_duration_seconds=int(os.getenv("MORTALCOIN_GAME_DURATION", "60")),
            monitor_interval_seconds=int(os.getenv("MORTALCOIN_MONITOR_INTERVAL", "5")),
            game_search_interval_seconds=int(os.getenv("MORTALCOIN_GAME_SEARCH_INTERVAL", "10")),
            pool_coin_id=int(os.getenv("MORTALCOIN_POOL_COIN_ID", "1")),
            db_path=os.getenv("MORTALCOIN_DB_PATH", "mortalcoin_bot.db"),
        )