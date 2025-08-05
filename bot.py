"""
Main bot class for MortalCoin Trading Bot.
"""

import asyncio
import logging
import signal
from typing import Optional

from config import BotConfig
from alith_client import AlithClient
from game_manager import GameManager
from database import GameDatabase


logger = logging.getLogger(__name__)


class MortalCoinBot:
    """Main bot class."""
    
    def __init__(self, config: BotConfig):
        self.config = config
        
        # Initialize components
        self.alith_client = AlithClient(
            openai_api_key=config.openai_api_key,
            model=config.alith_model
        )
        
        self.db = GameDatabase(config.db_path)
        
        self.game_manager = GameManager(
            config=config,
            alith_client=self.alith_client,
            db=self.db
        )
        
        self._stop_event = asyncio.Event()
        
    async def start(self):
        """Start the bot."""
        logger.info("Starting MortalCoin Trading Bot...")
        
        # Set up signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_signal)
            
        try:
            # Start game manager
            await self.game_manager.start()
            
        except Exception as e:
            logger.error(f"Bot error: {e}")
            raise
            
    async def stop(self):
        """Stop the bot."""
        logger.info("Stopping MortalCoin Trading Bot...")
        
        # Stop game manager
        await self.game_manager.stop()
        
        logger.info("Bot stopped")
        
    def _handle_signal(self):
        """Handle shutdown signal."""
        logger.info("Received shutdown signal")
        self._stop_event.set()
        
    async def run(self):
        """Run the bot."""
        try:
            # Start the bot
            bot_task = asyncio.create_task(self.start())
            
            # Wait for stop signal
            await self._stop_event.wait()
            
            # Stop the bot
            await self.stop()
            
            # Cancel the bot task
            bot_task.cancel()
            
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
                
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise
            
    def get_statistics(self) -> dict:
        """Get bot statistics."""
        return self.db.get_statistics()
        
    def get_game_history(self, limit: int = 100) -> list:
        """Get game history."""
        return self.db.get_game_history(limit)