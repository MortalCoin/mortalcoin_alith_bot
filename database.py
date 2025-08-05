"""
Database for storing game history and statistics.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class GameRecord:
    """Record of a game."""
    game_id: int
    bot_address: str
    opponent_address: str
    bet_amount: float
    started_at: datetime
    role: str  # "player1" or "player2"
    ended_at: Optional[datetime] = None
    final_pnl: Optional[float] = None
    result: Optional[str] = None  # "win", "loss", "draw"
    status: str = "active"  # "active", "completed", "error"
    

@dataclass
class PositionRecord:
    """Record of a position."""
    game_id: int
    direction: str  # "Long" or "Short"
    nonce: int
    opened_at: datetime
    reasoning: str
    closed_at: Optional[datetime] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    

class GameDatabase:
    """Database for game history and statistics."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Games table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    game_id INTEGER PRIMARY KEY,
                    bot_address TEXT NOT NULL,
                    opponent_address TEXT NOT NULL,
                    bet_amount REAL NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    role TEXT NOT NULL,
                    final_pnl REAL,
                    result TEXT,
                    status TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            # Positions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    direction TEXT NOT NULL,
                    nonce INTEGER NOT NULL,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    pnl REAL,
                    reasoning TEXT,
                    FOREIGN KEY (game_id) REFERENCES games (game_id)
                )
            """)
            
            # Statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    total_games INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    draws INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    avg_game_duration INTEGER DEFAULT 0,
                    total_positions INTEGER DEFAULT 0,
                    winning_positions INTEGER DEFAULT 0,
                    losing_positions INTEGER DEFAULT 0
                )
            """)
            
            conn.commit()
            
    def record_game(self, game: GameRecord):
        """Record a new game."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO games (
                    game_id, bot_address, opponent_address, bet_amount,
                    started_at, role, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                game.game_id,
                game.bot_address,
                game.opponent_address,
                game.bet_amount,
                game.started_at.isoformat(),
                game.role,
                game.status
            ))
            conn.commit()
            
    def update_game_status(self, game_id: int, status: str, final_pnl: Optional[float] = None):
        """Update game status."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if final_pnl is not None:
                result = "win" if final_pnl > 0 else "loss" if final_pnl < 0 else "draw"
                cursor.execute("""
                    UPDATE games 
                    SET status = ?, ended_at = ?, final_pnl = ?, result = ?
                    WHERE game_id = ?
                """, (status, datetime.now().isoformat(), final_pnl, result, game_id))
            else:
                cursor.execute("""
                    UPDATE games 
                    SET status = ?, ended_at = ?
                    WHERE game_id = ?
                """, (status, datetime.now().isoformat(), game_id))
                
            conn.commit()
            
    def record_position(self, position: PositionRecord):
        """Record a new position."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO positions (
                    game_id, direction, nonce, opened_at, reasoning
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                position.game_id,
                position.direction,
                position.nonce,
                position.opened_at.isoformat(),
                position.reasoning
            ))
            conn.commit()
            
    def close_position(self, game_id: int, nonce: int, exit_price: Optional[float] = None, pnl: Optional[float] = None):
        """Close a position."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE positions 
                SET closed_at = ?, exit_price = ?, pnl = ?
                WHERE game_id = ? AND nonce = ?
            """, (datetime.now().isoformat(), exit_price, pnl, game_id, nonce))
            conn.commit()
            
    def get_last_position(self, game_id: int) -> Optional[PositionRecord]:
        """Get the last position for a game."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT game_id, direction, nonce, opened_at, reasoning, closed_at, entry_price, exit_price, pnl
                FROM positions 
                WHERE game_id = ? 
                ORDER BY opened_at DESC 
                LIMIT 1
            """, (game_id,))
            
            row = cursor.fetchone()
            if row:
                return PositionRecord(
                    game_id=row[0],
                    direction=row[1],
                    nonce=row[2],
                    opened_at=datetime.fromisoformat(row[3]),
                    reasoning=row[4],
                    closed_at=datetime.fromisoformat(row[5]) if row[5] else None,
                    entry_price=row[6],
                    exit_price=row[7],
                    pnl=row[8]
                )
            return None
            
    def get_game_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get game history."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT game_id, bot_address, opponent_address, bet_amount,
                       started_at, ended_at, role, final_pnl, result, status
                FROM games 
                ORDER BY started_at DESC 
                LIMIT ?
            """, (limit,))
            
            games = []
            for row in cursor.fetchall():
                games.append({
                    "game_id": row[0],
                    "bot_address": row[1],
                    "opponent_address": row[2],
                    "bet_amount": row[3],
                    "started_at": row[4],
                    "ended_at": row[5],
                    "role": row[6],
                    "final_pnl": row[7],
                    "result": row[8],
                    "status": row[9]
                })
            return games
            
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Game statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_games,
                    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) as draws,
                    SUM(final_pnl) as total_pnl,
                    AVG(CASE 
                        WHEN ended_at IS NOT NULL 
                        THEN (julianday(ended_at) - julianday(started_at)) * 86400 
                        ELSE NULL 
                    END) as avg_game_duration_seconds
                FROM games 
                WHERE status = 'completed'
            """)
            
            game_stats = cursor.fetchone()
            
            # Position statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_positions,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_positions,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_positions,
                    AVG(pnl) as avg_position_pnl
                FROM positions 
                WHERE closed_at IS NOT NULL
            """)
            
            position_stats = cursor.fetchone()
            
            return {
                "games": {
                    "total": game_stats[0] or 0,
                    "wins": game_stats[1] or 0,
                    "losses": game_stats[2] or 0,
                    "draws": game_stats[3] or 0,
                    "total_pnl": game_stats[4] or 0,
                    "avg_duration_seconds": game_stats[5] or 0,
                    "win_rate": (game_stats[1] or 0) / (game_stats[0] or 1) if game_stats[0] else 0
                },
                "positions": {
                    "total": position_stats[0] or 0,
                    "winning": position_stats[1] or 0,
                    "losing": position_stats[2] or 0,
                    "avg_pnl": position_stats[3] or 0,
                    "win_rate": (position_stats[1] or 0) / (position_stats[0] or 1) if position_stats[0] else 0
                }
            }