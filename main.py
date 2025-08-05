"""
Main entry point for MortalCoin Trading Bot.
"""

import asyncio
import logging
import sys
from typing import Optional

import click
from dotenv import load_dotenv

from bot import MortalCoinBot
from config import BotConfig


class ColoredFormatter(logging.Formatter):
    """Custom colored formatter for MortalCoin bot logs."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    
    # Component colors
    COMPONENT_COLORS = {
        'bot': '\033[94m',           # Blue
        'game_manager': '\033[93m',  # Yellow
        'websocket_client': '\033[95m',  # Magenta
        'backend_client': '\033[96m',    # Cyan
        'blockchain': '\033[92m',        # Green
        'alith_client': '\033[91m',      # Red
        'database': '\033[90m',          # Dark gray
    }
    
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def format(self, record):
        # Get base color for log level
        level_color = self.COLORS.get(record.levelname, '')
        
        # Get component color
        component_name = record.name.split('.')[-1] if '.' in record.name else record.name
        component_color = self.COMPONENT_COLORS.get(component_name, '')
        
        # Format timestamp
        timestamp = self.formatTime(record)
        
        # Format the message
        if level_color or component_color:
            # Colorized format
            formatted = f"{self.BOLD}{level_color}[{record.levelname}]{self.RESET} "
            formatted += f"{component_color}[{component_name}]{self.RESET} "
            formatted += f"{timestamp} - {record.getMessage()}"
        else:
            # Fallback to standard format
            formatted = f"[{record.levelname}] [{component_name}] {timestamp} - {record.getMessage()}"
        
        return formatted


def setup_logging():
    """Setup colored logging for the bot."""
    # Create formatter
    formatter = ColoredFormatter()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    
    # Disable propagation for some noisy loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)


@click.group()
def cli():
    """MortalCoin Trading Bot CLI."""
    pass


@cli.command()
def run():
    """Run the MortalCoin Trading Bot."""
    setup_logging()
    
    # Load environment variables
    load_dotenv()
    
    # Load configuration
    config = BotConfig.from_env()
    
    # Create and start bot
    bot = MortalCoinBot(config)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n\033[93m[INFO] Shutting down bot...\033[0m")
    except Exception as e:
        print(f"\n\033[31m[ERROR] Bot crashed: {e}\033[0m")
        raise


if __name__ == "__main__":
    cli()