"""
JALWE AI TRADER V3
Database Persistence Module
"""
import sqlite3
import os
from datetime import datetime

DB_FILE = "jalwe_trader.db"

class DatabaseManager:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize SQLite database with WAL mode and automatic column migration for all tables."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Enable WAL mode for high concurrency
        cursor.execute("PRAGMA journal_mode=WAL;")
        
        # Opportunities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                action TEXT,
                confidence REAL,
                price REAL,
                details TEXT
            )
        """)
        
        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                side TEXT,
                qty REAL,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                status TEXT
            )
        """)
        
        # Safely ensure required columns exist in opportunities table
        for col_name, col_type in [("price", "REAL"), ("confidence", "REAL"), ("details", "TEXT"), ("action", "TEXT"), ("symbol", "TEXT"), ("timestamp", "TEXT")]:
            try:
                cursor.execute(f"ALTER TABLE opportunities ADD COLUMN {col_name} {col_type};")
            except sqlite3.OperationalError:
                pass

        # Safely ensure required columns exist in trades table
        for col_name, col_type in [("side", "TEXT"), ("qty", "REAL"), ("entry_price", "REAL"), ("stop_loss", "REAL"), ("take_profit", "REAL"), ("status", "TEXT"), ("symbol", "TEXT"), ("timestamp", "TEXT")]:
            try:
                cursor.execute(f"ALTER TABLE trades ADD COLUMN {col_name} {col_type};")
            except sqlite3.OperationalError:
                pass
        
        conn.commit()
        conn.close()

    def log_opportunity(self, symbol: str, action: str, confidence: float, price: float, details: str = ""):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO opportunities (timestamp, symbol, action, confidence, price, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), symbol, action, confidence, price, details))
        conn.commit()
        conn.close()

    def save_opportunity(self, opportunity):
        if isinstance(opportunity, dict):
            symbol = opportunity.get("symbol", "UNKNOWN")
            action = opportunity.get("action", "BUY")
            confidence = opportunity.get("confidence", 0.0)
            price = opportunity.get("price", 0.0)
            details = str(opportunity)
        else:
            symbol = getattr(opportunity, "symbol", "UNKNOWN")
            action = getattr(opportunity, "action", "BUY")
            confidence = getattr(opportunity, "confidence", 0.0)
            price = getattr(opportunity, "price", 0.0)
            details = str(opportunity)
            
        self.log_opportunity(symbol, action, confidence, price, details)

    def log_trade(self, symbol: str, side: str, qty: float, entry_price: float, stop_loss: float, take_profit: float, status: str = "OPEN"):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trades (timestamp, symbol, side, qty, entry_price, stop_loss, take_profit, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), symbol, side, qty, entry_price, stop_loss, take_profit, status))
        conn.commit()
        conn.close()

# Alias for backward compatibility
Database = DatabaseManager