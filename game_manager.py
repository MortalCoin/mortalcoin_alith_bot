"""
Game manager for handling game lifecycle.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime, timedelta
import random

from web3 import Web3
from web3.contract import Contract

from blockchain import (
    get_web3_connection,
    get_contract,
    get_game_info,
    Direction,
    get_active_games,
    get_player_game_info,
)
from blockchain.transactions import build_sign_send_transaction

from config import BotConfig
from alith_client import AlithClient, MarketData, GameState, TradingDecision
from database import GameDatabase, GameRecord, PositionRecord
from backend_client import BackendClient
from price_feed import PriceFeedManager
from websocket_client import WebSocketClient


logger = logging.getLogger(__name__)


class GameManager:
    """Manages game lifecycle and trading decisions."""
    
    def __init__(self, config: BotConfig, alith_client: AlithClient, db: GameDatabase):
        self.config = config
        self.alith_client = alith_client
        self.db = db
        
        # Initialize blockchain connection
        self.web3 = get_web3_connection(config.rpc_url)
        self.contract = get_contract(self.web3, config.contract_address)
        
        # Get bot address
        self.bot_account = self.web3.eth.account.from_key(config.bot_private_key)
        self.bot_address = self.bot_account.address
        
        # Initialize backend client
        self.backend_client = BackendClient(config.backend_api_url, self.bot_address, config.privy_key)
        
        # Initialize WebSocket client for notifications
        ws_url = config.backend_api_url.replace("https://", "wss://").replace("http://", "ws://") + "/ws/users/notifications/"
        self.websocket_client = WebSocketClient(ws_url, "")
        
        # Initialize price feed manager
        self.price_feed_manager = PriceFeedManager(self.web3, self.contract, self.backend_client)
        
        # Track active games
        self.active_games: Dict[int, asyncio.Task] = {}
        
        # Running flag
        self.running = False
        

        
    async def start(self):
        """Start the game manager."""
        logger.info(f"\033[94m🚀 Starting game manager for bot address: {self.bot_address}\033[0m")
        self.running = True
        
        # Initialize backend client session
        await self.backend_client.__aenter__()
        
        # Authenticate to get JWT token
        await self.backend_client._authenticate()
        
        # Connect to WebSocket for notifications
        self.websocket_client.auth_token = self.backend_client.auth_token
        if await self.websocket_client.connect():
            # Add handlers for different message types
            self.websocket_client.add_message_handler("signature_ready", self._handle_signature_ready)
            self.websocket_client.add_message_handler("game_joined", self._handle_game_joined)
            
            # Start WebSocket listener
            self.websocket_task = asyncio.create_task(self.websocket_client.listen())
        
        # Start monitoring loop
        monitor_task = asyncio.create_task(self._monitor_games())
        
        try:
            await monitor_task
        except asyncio.CancelledError:
            logger.info("\033[93m🛑 Game manager stopped\033[0m")
            
    async def stop(self):
        """Stop the game manager."""
        logger.info("Stopping game manager...")
        self.running = False
        
        # Cancel all active game tasks
        for game_id, task in self.active_games.items():
            logger.info(f"Cancelling game {game_id}")
            task.cancel()
            
        # Wait for all tasks to complete
        if self.active_games:
            await asyncio.gather(*self.active_games.values(), return_exceptions=True)
            
        # Disconnect from WebSocket
        if hasattr(self, 'websocket_task'):
            self.websocket_task.cancel()
            await self.websocket_client.disconnect()
            
        # Clean up backend client session
        await self.backend_client.__aexit__(None, None, None)
            
        logger.info("Game manager stopped")
        
    async def _monitor_games(self):
        """Monitor for available games to join."""
        logger.info("\033[92m🔄 Starting game monitoring loop...\033[0m")
        last_ws_status_time = 0
        ws_status_interval = 5  # Log WebSocket status every 5 seconds
        
        while self.running:
            try:
                # Log WebSocket status periodically
                current_time = time.time()
                if current_time - last_ws_status_time >= ws_status_interval:
                    logger.info(f"\033[96m📊 Status: {self.websocket_client.get_status_info()}\033[0m")
                    last_ws_status_time = current_time
                
                # Check if bot is already in a game
                player_info = get_player_game_info(self.contract, self.bot_address)
                logger.info(f"\033[93m👤 Player info: {player_info}\033[0m")
                
                if not player_info["inGame"]:
                    # Bot is not in a game, look for games to join
                    logger.info("\033[33m🔍 Bot not in game, searching for games to join...\033[0m")
                    if not self.active_games:  # No active game being tracked
                        await self._find_and_join_game()
                else:
                    # Bot is in a game, make sure we're tracking it
                    game_id = player_info["gameId"]
                    logger.info(f"\033[92m🎮 Bot is in game {game_id}\033[0m")
                    if game_id not in self.active_games:
                        logger.info(f"\033[94m🎯 Found existing game {game_id}, starting game loop\033[0m")
                        task = asyncio.create_task(self._game_loop(game_id))
                        self.active_games[game_id] = task
                
                # Clean up completed games
                completed_games = []
                for game_id, task in self.active_games.items():
                    if task.done():
                        completed_games.append(game_id)
                        
                for game_id in completed_games:
                    del self.active_games[game_id]
                    
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                
            # Use different intervals based on whether we're in a game or searching
            if self.active_games:
                # In game - monitor more frequently
                logger.debug(f"Sleeping {self.config.monitor_interval_seconds}s (in game)")
                await asyncio.sleep(self.config.monitor_interval_seconds)
            else:
                # Searching for games - can be less frequent
                logger.debug(f"Sleeping {self.config.game_search_interval_seconds}s (searching)")
                await asyncio.sleep(self.config.game_search_interval_seconds)

    async def _find_and_join_game(self):
        """Find and join an available game."""
        try:
            # Use backend API to get available games
            logger.info("Fetching available games from backend API...")
            available_games = await self.backend_client.get_available_games()

            if not available_games:
                logger.info("No available games from backend API")
                return

            logger.info(f"Found {len(available_games)} available games from backend")

            for game_data in available_games:
                try:
                    # Backend returns UUID in 'id' field - use it as game_id like frontend does
                    game_id = game_data.get("id")  # Use UUID as game_id
                    if game_id is None:
                        logger.debug(f"No id found in game_data: {game_data}")
                        continue
                        
                    logger.info(f"Found game with UUID game_id: {game_id}")
                    
                    # Join the game using UUID (like frontend does)
                    logger.info(f"Found joinable game {game_id} from backend API")
                    
                    # Join the game
                    await self._join_game(game_id, game_data)
                    return
                            
                except Exception as e:
                    logger.error(f"Error checking game from backend: {e}")
                    continue

            logger.info("No suitable games found from backend API")

        except Exception as e:
            logger.error(f"Error finding games via backend API: {e}")
            logger.info("No games available from backend API")
            

            
    async def _join_game(self, game_id: str, game_data: Dict):
        """Join a specific game using UUID from backend."""
        try:
            logger.info(f"\033[94m🎯 Attempting to join game {game_id}\033[0m")
            
            # Get player1's address from creator_id in game_data
            creator_id = game_data.get("creator_id")
            if not creator_id:
                logger.error(f"\033[31m❌ No creator_id found in game_data: {game_data}\033[0m")
                return
            
            # Set signature expiration (current time + 5 minutes)
            signature_expiration = int(time.time()) + 300
            
            # Add opponent to fight using backend API (like frontend does)
            result = await self.backend_client.add_opponent_to_fight(
                game_id=game_id,
                player_address=self.bot_address,
                coin_id=self.config.pool_coin_id
            )
            
            if not result:
                logger.error(f"\033[31m❌ Failed to add opponent to fight for game {game_id}\033[0m")
                return
                
            logger.info(f"\033[92m✅ Successfully added opponent to fight: {game_id}\033[0m")
            logger.info(f"\033[93m📋 Result: {result}\033[0m")
            
            # TODO: After adding opponent, we need to handle the actual blockchain join
            # This might involve getting the numeric game_id and calling joinGame on contract
            logger.info(f"\033[94m🚀 Successfully joined game via backend API\033[0m")
            
        except Exception as e:
            logger.error(f"\033[31m❌ Error joining game {game_id}: {e}\033[0m")
            
    async def _handle_signature_ready(self, data: Dict[str, Any]):
        """Handle signature ready notification from WebSocket."""
        try:
            logger.info(f"\033[94m📝 Received signature ready notification: {data}\033[0m")
            
            # Extract signature data from the received message
            signature = data.get("signature")
            original_request = data.get("original_request")
            
            if not signature or not original_request:
                logger.error(f"\033[31m❌ Missing required fields in signature notification: {data}\033[0m")
                return
                
            # Extract game info from original request
            game_id = original_request.get("game_id")
            player2 = original_request.get("player2")
            timestamp = original_request.get("timestamp")
            ttl = original_request.get("ttl")
            
            if not all([game_id, player2, timestamp, ttl]):
                logger.error(f"\033[31m❌ Missing required fields in original request: {original_request}\033[0m")
                return
                
            logger.info(f"\033[92m🎯 Processing signature for game {game_id}\033[0m")
            logger.info(f"\033[93m📋 Signature: {signature[:20]}...\033[0m")
            logger.info(f"\033[93m👤 Player2: {player2}\033[0m")
            logger.info(f"\033[93m⏰ Timestamp: {timestamp}, TTL: {ttl}\033[0m")
            
            # Call joinGame on blockchain
            try:
                # Convert game_id to int (it comes as string from backend)
                numeric_game_id = int(game_id)
                
                # Get pool address from config
                pool_address = self.config.bot_pool_address
                
                # Calculate signature expiration
                signature_expiration = timestamp + ttl
                
                # Convert signature from hex string to bytes
                signature_bytes = bytes.fromhex(signature.replace("0x", ""))
                
                logger.info(f"\033[94m🚀 Calling joinGame on blockchain...\033[0m")
                logger.info(f"\033[93m📊 Game ID: {numeric_game_id}\033[0m")
                logger.info(f"\033[93m🏊 Pool: {pool_address}\033[0m")
                logger.info(f"\033[93m⏰ Expiration: {signature_expiration}\033[0m")
                
                # Build joinGame transaction
                join_game_function = self.contract.functions.joinGame(
                    numeric_game_id,
                    pool_address,
                    signature_expiration,
                    signature_bytes
                )
                
                # Send transaction
                tx_hash, receipt = build_sign_send_transaction(
                    self.web3,
                    join_game_function,
                    self.config.bot_private_key,
                    {'value': self.web3.to_wei(self.config.bet_amount_eth, 'ether')}
                )
                
                logger.info(f"\033[92m✅ Successfully called joinGame! Transaction: {tx_hash}\033[0m")
                logger.info(f"\033[93m📋 Gas used: {receipt['gasUsed']}\033[0m")
                
                # Notify backend about successful join
                await self.backend_client.notify_game_joined(numeric_game_id, tx_hash)
                
            except Exception as e:
                logger.error(f"\033[31m❌ Error calling joinGame: {e}\033[0m")
            
        except Exception as e:
            logger.error(f"\033[31m❌ Error handling signature ready notification: {e}\033[0m")
            
    async def _handle_game_joined(self, data: Dict[str, Any]):
        """Handle game joined notification from WebSocket."""
        try:
            logger.info(f"\033[94m🎮 Received game joined notification: {data}\033[0m")
            
            # Extract game data
            game_id = data.get("game_id")
            player_address = data.get("player_address")
            
            if not all([game_id, player_address]):
                logger.error(f"\033[31m❌ Missing required fields in game joined notification: {data}\033[0m")
                return
                
            logger.info(f"\033[92m🎯 Game {game_id} joined by {player_address}\033[0m")
            
            # TODO: Start game loop if we joined the game
            # This will be implemented once we have the complete flow
            logger.info(f"\033[94m🚀 Ready to start game loop for game {game_id}\033[0m")
            
        except Exception as e:
            logger.error(f"\033[31m❌ Error handling game joined notification: {e}\033[0m")
            
    async def _game_loop(self, game_id: int):
        """Main game loop for a specific game."""
        logger.info(f"\033[94m🎮 Starting game loop for game {game_id}\033[0m")
        
        try:
            game_start_time = datetime.now()
            current_position = None
            position_entry_price = None
            position_open_time = None
            
            while self.running:
                try:
                    # Get current game info
                    game_info = get_game_info(self.contract, game_id)
                    
                    # Log game state for debugging
                    logger.info(f"\033[96m🔍 Game {game_id} state: {game_info['state']}\033[0m")
                    logger.info(f"\033[96m🔍 Game end timestamp: {game_info['gameEndTimestamp']}\033[0m")
                    logger.info(f"\033[96m🔍 Current time: {int(time.time())}\033[0m")
                    logger.info(f"\033[96m🔍 Player1: {game_info['player1']}\033[0m")
                    logger.info(f"\033[96m🔍 Player2: {game_info['player2']}\033[0m")
                    logger.info(f"\033[96m🔍 Bet amount: {game_info['betAmount']}\033[0m")
                    logger.info(f"\033[96m🔍 Player1 PnL: {game_info['player1Pnl']}\033[0m")
                    logger.info(f"\033[96m🔍 Player2 PnL: {game_info['player2Pnl']}\033[0m")
                    logger.info(f"\033[96m🔍 Player1 position state: {game_info['player1Position']['state']}\033[0m")
                    logger.info(f"\033[96m🔍 Player2 position state: {game_info['player2Position']['state']}\033[0m")
                    
                    # Check if game has ended (state == 3 = Finished)
                    if game_info["state"] == 3:  # Finished state
                        logger.info(f"\033[93m🏁 Game {game_id} has finished\033[0m")
                        break
                        
                    # Check if game is in Started state (state == 2)
                    if game_info["state"] != 2:  # Started state
                        logger.info(f"\033[33m⏳ Game {game_id} not in Started state yet (state: {game_info['state']})\033[0m")
                        await asyncio.sleep(1)
                        continue
                        
                    # Check if game timeout reached (60 seconds from start)
                    if game_info["gameEndTimestamp"] > 0 and time.time() > game_info["gameEndTimestamp"]:
                        logger.info(f"\033[93m⏰ Game {game_id} reached timeout, finishing...\033[0m")
                        await self._finish_game(game_id, current_position)
                        break
                        
                    # Auto-close position if less than 5 seconds remaining
                    if game_info["gameEndTimestamp"] > 0 and current_position:
                        time_until_end = game_info["gameEndTimestamp"] - time.time()
                        if time_until_end <= 5:
                            logger.info(f"\033[93m⏰ Auto-closing position - {time_until_end:.1f}s until game end\033[0m")
                            # Force close position decision
                            close_decision = TradingDecision(
                                action="close_position",
                                reasoning="Auto-close: less than 5 seconds remaining",
                                confidence=1.0
                            )
                            await self._execute_decision(game_id, close_decision, current_position, position_open_time)
                            current_position = None
                            position_entry_price = None
                            position_open_time = None
                            continue
                        
                    # Determine which pool we're using
                    if game_info["player1"].lower() == self.bot_address.lower():
                        my_pool = game_info["player1Pool"]
                        opponent_pool = game_info["player2Pool"]
                    else:
                        my_pool = game_info["player2Pool"]
                        opponent_pool = game_info["player1Pool"]
                        
                    # Get market data from our pool
                    market_data = await self._get_market_data(my_pool)
                    
                    # Calculate game state
                    time_elapsed = (datetime.now() - game_start_time).total_seconds()
                    time_remaining = max(0, self.config.game_duration_seconds - time_elapsed)
                    
                    # Determine opponent info
                    if game_info["player1"].lower() == self.bot_address.lower():
                        opponent_address = game_info["player2"]
                        opponent_position = game_info["player2Position"]
                        my_pnl = game_info["player1Pnl"]
                        opponent_pnl = game_info["player2Pnl"]
                    else:
                        opponent_address = game_info["player1"]
                        opponent_position = game_info["player1Position"]
                        my_pnl = game_info["player2Pnl"]
                        opponent_pnl = game_info["player1Pnl"]
                        
                    # Log game state
                    logger.info(f"\033[96m📊 Game {game_id} - Time remaining: {time_remaining:.1f}s, My PnL: {my_pnl}, Opponent PnL: {opponent_pnl}\033[0m")
                    
                    # Determine opponent position state
                    opponent_has_position = opponent_position["state"] == 1  # Open state (PositionState.Open)
                    
                    # Create game state for AI
                    game_state = GameState(
                        game_id=game_id,
                        opponent_address=opponent_address,
                        opponent_has_position=opponent_has_position,
                        opponent_pnl=Web3.from_wei(opponent_pnl, "ether"),
                        my_pnl=Web3.from_wei(my_pnl, "ether"),
                        time_remaining_seconds=int(time_remaining),
                        my_position=current_position,
                        my_position_entry_price=position_entry_price
                    )
                    
                    # Get trading decision from Alith AI
                    logger.info(f"\033[94m🤖 Getting AI trading decision...\033[0m")
                    decision = self.alith_client.get_trading_decision(market_data, game_state)
                    logger.info(f"\033[93m🎯 AI Decision: {decision.action} - {decision.reasoning}\033[0m")
                    
                    # Execute trading decision
                    await self._execute_decision(game_id, decision, current_position, position_open_time)
                    
                    # Update position tracking
                    if decision.action == "open_long":
                        current_position = "long"
                        position_entry_price = market_data.current_price
                        position_open_time = datetime.now()
                        logger.info(f"\033[92m📈 Opened LONG position at {position_entry_price}\033[0m")
                    elif decision.action == "open_short":
                        current_position = "short"
                        position_entry_price = market_data.current_price
                        position_open_time = datetime.now()
                        logger.info(f"\033[92m📉 Opened SHORT position at {position_entry_price}\033[0m")
                    elif decision.action == "close_position" and current_position:
                        logger.info(f"\033[93m🔒 Closing {current_position.upper()} position\033[0m")
                        current_position = None
                        position_entry_price = None
                        position_open_time = None
                    
                    # Sleep for a short interval
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"\033[31m❌ Error in game loop iteration: {e}\033[0m")
                    await asyncio.sleep(5)  # Wait longer on error
                    
        except Exception as e:
            logger.error(f"\033[31m❌ Error in game loop for game {game_id}: {e}\033[0m")
        finally:
            logger.info(f"\033[93m🛑 Game loop ended for game {game_id}\033[0m")
            
    async def _get_market_data(self, pool_address: str) -> MarketData:
        """Get current market data from Uniswap V2 pool."""
        return await self.price_feed_manager.get_market_data(pool_address)
        
    async def _execute_decision(
        self,
        game_id: int,
        decision: TradingDecision,
        current_position: Optional[str],
        position_open_time: Optional[datetime]
    ):
        """Execute a trading decision."""
        try:
            if decision.action in ["open_long", "open_short"] and not current_position:
                # Open a new position
                direction = Direction.Long if decision.action == "open_long" else Direction.Short
                nonce = random.randint(1, 1000000)
                
                logger.info(f"\033[94m📈 Opening {direction.name} position in game {game_id}\033[0m")
                logger.info(f"\033[93m🎲 Generated nonce: {nonce}\033[0m")
                
                # Calculate hashed direction
                from eth_abi import encode
                encoded_data = encode(['uint256', 'uint8', 'uint256'], [game_id, direction, nonce])
                hashed_direction = self.web3.keccak(encoded_data)
                
                logger.info(f"\033[93m🔐 Hashed direction: {hashed_direction.hex()}\033[0m")
                
                # Get backend signature
                logger.info(f"\033[93m🔐 Getting backend signature for position...\033[0m")
                backend_signature = await self.backend_client.get_post_position_signature(
                    game_id=game_id,
                    player_address=self.bot_address,
                    hashed_direction=hashed_direction
                )
                
                if not backend_signature:
                    logger.error(f"\033[31m❌ Failed to get backend signature for position\033[0m")
                    return
                    
                logger.info(f"\033[92m✅ Got backend signature, ready to post position...\033[0m")
                logger.info(f"\033[93m📋 Backend signature: {backend_signature.hex()}\033[0m")
                
                # Build and send transaction
                post_position_function = self.contract.functions.postPosition(
                    game_id,
                    hashed_direction,
                    backend_signature
                )
                
                tx_hash, receipt = build_sign_send_transaction(
                    self.web3,
                    post_position_function,
                    self.config.bot_private_key
                )
                
                logger.info(f"\033[92m✅ Position opened successfully! Transaction: {tx_hash}\033[0m")
                logger.info(f"\033[93m📋 Gas used: {receipt['gasUsed']}\033[0m")
                
                # Record position (even without broadcasting)
                position_record = PositionRecord(
                    game_id=game_id,
                    direction=direction.name,
                    nonce=nonce,
                    opened_at=datetime.now(),
                    reasoning=decision.reasoning
                )
                self.db.record_position(position_record)
                logger.info(f"\033[92m💾 Position recorded in database with nonce: {nonce}\033[0m")
                
            elif decision.action == "close_position" and current_position:
                # Check minimum hold time
                if position_open_time:
                    hold_time = (datetime.now() - position_open_time).total_seconds()
                    if hold_time < self.config.position_hold_time_min:
                        logger.debug(f"\033[33m⏳ Position held for {hold_time}s, waiting for minimum {self.config.position_hold_time_min}s\033[0m")
                        return
                        
                # Close current position
                direction = Direction.Long if current_position == "long" else Direction.Short
                
                logger.info(f"\033[94m🔒 Closing {direction.name} position in game {game_id}\033[0m")
                
                # Build and send close position transaction
                close_position_function = self.contract.functions.closePosition(game_id)
                
                tx_hash, receipt = build_sign_send_transaction(
                    self.web3,
                    close_position_function,
                    self.config.bot_private_key
                )
                
                logger.info(f"\033[92m✅ Position closed successfully! Transaction: {tx_hash}\033[0m")
                logger.info(f"\033[93m📋 Gas used: {receipt['gasUsed']}\033[0m")
                
            else:
                logger.info(f"\033[33m⏸️  No action taken: {decision.action}\033[0m")
                
        except Exception as e:
            logger.error(f"\033[31m❌ Error executing decision: {e}\033[0m")
            
    async def _finish_game(self, game_id: int, current_position: Optional[str]):
        """Finish a game."""
        try:
            logger.info(f"Finishing game {game_id}")
            
            # If we have an open position, we need to provide direction and nonce
            if current_position:
                direction = Direction.Long if current_position == "long" else Direction.Short
                last_position = self.db.get_last_position(game_id)
                nonce = last_position.nonce if last_position else 0
            else:
                direction = Direction.Long  # Default
                nonce = 0
                
            # Build and send finish game transaction
            tx_params = {'from': self.bot_address}
            
            tx_hash, receipt = await asyncio.get_event_loop().run_in_executor(
                None,
                build_sign_send_transaction,
                self.web3,
                self.contract.functions.finishGame(
                    game_id,
                    direction,
                    nonce
                ),
                self.config.bot_private_key,
                tx_params
            )
            
            logger.info(f"Game finished, tx: {tx_hash}")
            
        except Exception as e:
            logger.error(f"Error finishing game {game_id}: {e}")