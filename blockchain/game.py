"""
Game-related blockchain functions.
"""

from enum import IntEnum
from typing import Dict, Any, Optional

from web3 import Web3
from web3.contract import Contract


class Direction(IntEnum):
    """Trading direction enum."""
    Long = 0
    Short = 1


def get_game_info(contract: Contract, game_id: int) -> Dict[str, Any]:
    """Get game information from contract."""
    game_info = contract.functions.games(game_id).call()
    
    return {
        "betAmount": game_info[0],
        "player1": game_info[1],
        "gameEndTimestamp": game_info[2],
        "player1Pool": game_info[3],
        "player2": game_info[4],
        "player2Pool": game_info[5],
        "state": game_info[6],
        "player1Position": {
            "openingPrice": game_info[7][0],
            "hashedDirection": game_info[7][1].hex(),
            "state": game_info[7][2]
        },
        "player2Position": {
            "openingPrice": game_info[8][0],
            "hashedDirection": game_info[8][1].hex(),
            "state": game_info[8][2]
        },
        "player1Pnl": game_info[9],
        "player2Pnl": game_info[10]
    }


def get_active_games(contract: Contract) -> int:
    """Get number of active games."""
    return contract.functions.activeGames().call()


def get_player_game_info(contract: Contract, player_address: str) -> Dict[str, Any]:
    """Get player's game information."""
    info = contract.functions.playerGameInfo(Web3.to_checksum_address(player_address)).call()
    
    return {
        "inGame": info[0],
        "gameId": info[1],
        "role": info[2]  # 0: None, 1: Creator, 2: Participant
    }