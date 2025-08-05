"""
Alith AI client for trading decisions.
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from alith import Agent


logger = logging.getLogger(__name__)


@dataclass
class MarketData:
    """Market data for decision making."""
    current_price: float
    price_history: list[float]  # Recent price history
    timestamp: datetime
    
    
@dataclass
class GameState:
    """Current game state."""
    game_id: int
    opponent_address: str
    opponent_has_position: bool
    opponent_pnl: float
    my_pnl: float
    time_remaining_seconds: int
    my_position: Optional[str] = None  # "long", "short", or None
    my_position_entry_price: Optional[float] = None
    

@dataclass
class TradingDecision:
    """Trading decision from Alith AI."""
    action: str  # "open_long", "open_short", "close_position", "hold"
    reasoning: str
    confidence: float  # 0.0 to 1.0


class AlithClient:
    """Client for interacting with Alith AI."""
    
    def __init__(self, openai_api_key: str, model: str = "gpt-4"):
        # Set OpenAI API key for Alith
        os.environ["OPENAI_API_KEY"] = openai_api_key
        
        # Initialize Alith Agent
        self.agent = Agent(
            name="MortalCoin Trading Bot",
            model=model,
            preamble="""You are an expert crypto trader playing a PvP trading game called MortalCoin. 
Your goal is to maximize profit and beat your opponent by making strategic trading decisions.

You have access to real-time market data and game state information. You can:
- Open long positions (betting price will go up)
- Open short positions (betting price will go down)  
- Close existing positions
- Hold/wait for better opportunities

Always consider:
1. Market momentum and trends
2. Risk/reward ratios
3. Time remaining in the game
4. Your current P&L vs opponent
5. Optimal position sizing and timing

Respond with clear, actionable trading decisions based on the provided data.""",
        )
        
    def get_trading_decision(
        self,
        market_data: MarketData,
        game_state: GameState,
    ) -> TradingDecision:
        """Get trading decision from Alith AI."""
        
        # Prepare context for Alith AI
        context = self._prepare_context(market_data, game_state)
        
        # Create prompt
        prompt = self._create_trading_prompt(context)
        
        try:
            # Use Alith Agent to get response
            response = self.agent.prompt(prompt)
            
            # Parse response
            decision = self._parse_response(response)
            
            logger.info(f"Alith AI decision: {decision.action} (confidence: {decision.confidence})")
            logger.debug(f"Reasoning: {decision.reasoning}")
            
            return decision
            
        except Exception as e:
            logger.error(f"Error getting Alith AI decision: {e}")
            # Return a safe default decision
            return TradingDecision(
                action="hold",
                reasoning="Error in AI decision, holding position",
                confidence=0.0
            )
    
    def _prepare_context(self, market_data: MarketData, game_state: GameState) -> Dict[str, Any]:
        """Prepare context data for AI decision."""
        
        # Calculate price trend
        price_change = 0.0
        if len(market_data.price_history) >= 2:
            price_change = (market_data.current_price - market_data.price_history[-2]) / market_data.price_history[-2] * 100
        
        # Calculate current P&L if position is open
        current_pnl_pct = 0.0
        if game_state.my_position and game_state.my_position_entry_price:
            if game_state.my_position == "long":
                current_pnl_pct = (market_data.current_price - game_state.my_position_entry_price) / game_state.my_position_entry_price * 100
            else:  # short
                current_pnl_pct = (game_state.my_position_entry_price - market_data.current_price) / game_state.my_position_entry_price * 100
        
        return {
            "market": {
                "current_price": market_data.current_price,
                "price_history": market_data.price_history[-10:],  # Last 10 prices
                "price_change_pct": price_change,
                "timestamp": market_data.timestamp.isoformat(),
            },
            "game": {
                "game_id": game_state.game_id,
                "time_remaining_seconds": game_state.time_remaining_seconds,
                "my_pnl": game_state.my_pnl,
                "opponent_pnl": game_state.opponent_pnl,
                "opponent_has_position": game_state.opponent_has_position,
                "pnl_difference": game_state.my_pnl - game_state.opponent_pnl,
            },
            "position": {
                "current_position": game_state.my_position,
                "entry_price": game_state.my_position_entry_price,
                "current_pnl_pct": current_pnl_pct,
            }
        }
    
    def _create_trading_prompt(self, context: Dict[str, Any]) -> str:
        """Create prompt for Alith AI."""
        
        prompt = f"""You are an expert crypto trader playing a PvP trading game. Your goal is to maximize profit and beat your opponent.

Current Market Data:
- Current Price: ${context['market']['current_price']:.2f}
- Price Change: {context['market']['price_change_pct']:.2f}%
- Recent Prices: {context['market']['price_history']}

Game State:
- Time Remaining: {context['game']['time_remaining_seconds']} seconds
- Your P&L: ${context['game']['my_pnl']:.2f}
- Opponent P&L: ${context['game']['opponent_pnl']:.2f}
- P&L Difference: ${context['game']['pnl_difference']:.2f}
- Opponent Has Position: {context['game']['opponent_has_position']}

Your Position:
- Current Position: {context['position']['current_position'] or 'None'}
- Entry Price: {f"${context['position']['entry_price']:.2f}" if context['position']['entry_price'] else 'N/A'}
- Current P&L %: {context['position']['current_pnl_pct']:.2f}%

Based on this information, what trading action should I take? Consider:
1. Market momentum and trend
2. Risk/reward ratio
3. Time remaining in the game
4. Current P&L vs opponent
5. Whether to open a new position, close existing, or hold

Respond with a JSON object containing:
- "action": one of ["open_long", "open_short", "close_position", "hold"]
- "reasoning": brief explanation of your decision
- "confidence": confidence level from 0.0 to 1.0
"""
        
        return prompt
    

    def _parse_response(self, response: str) -> TradingDecision:
        """Parse Alith AI response into TradingDecision."""
        
        try:
            # The response is now a direct string from alith agent
            content = response
            
            # Try to parse JSON from the content
            # Look for JSON block in the response
            import re
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            
            if json_match:
                decision_data = json.loads(json_match.group())
            else:
                # Try to parse the entire content as JSON
                decision_data = json.loads(content)
            
            return TradingDecision(
                action=decision_data.get("action", "hold"),
                reasoning=decision_data.get("reasoning", "No reasoning provided"),
                confidence=float(decision_data.get("confidence", 0.5))
            )
            
        except Exception as e:
            logger.error(f"Error parsing Alith response: {e}")
            logger.debug(f"Raw response: {response}")
            
            # Try to extract action from text
            content_lower = content.lower()
            if "open long" in content_lower:
                action = "open_long"
            elif "open short" in content_lower:
                action = "open_short"
            elif "close" in content_lower:
                action = "close_position"
            else:
                action = "hold"
            
            return TradingDecision(
                action=action,
                reasoning="Parsed from text response",
                confidence=0.3
            )