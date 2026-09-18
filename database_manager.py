import sqlite3
import pandas as pd
import json
import logging
import os

class DatabaseManager:
    def __init__(self, db_name="jalwe_ai_trader.db"):
        self.db_name = db_name
        self.init_database()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_database(self):
        """
        Initializes the database schema for trades, features, models, and strategies.
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Trades & Execution Memory
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    side TEXT,
                    qty INTEGER,
                    entry_price REAL,
                    exit_price REAL,
                    pnl REAL,
                    status TEXT,
                    timestamp TEXT,
                    features_snapshot TEXT
                )
            """)

            # Feature Store for AI Learning
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feature_store (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    timestamp TEXT,
                    features_json TEXT,
                    regime TEXT
                )
            """)

            # Strategy Registry & Versions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT,
                    version TEXT,
                    parameters TEXT,
                    status TEXT,
                    metrics TEXT,
                    updated_at TEXT
                )
            """)

            conn.commit()
            conn.close()
            logging.info("Database schema initialized successfully.")
        except Exception as e:
            logging.error(f"Error initializing database: {e}")

    def log_trade(self, symbol, side, qty, entry_price, status, features=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        features_str = json.dumps(features) if features else "{}"
        cursor.execute("""
            INSERT INTO trades (symbol, side, qty, entry_price, status, timestamp, features_snapshot)
            VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
        """, (symbol, side, qty, entry_price, status, features_str))
        conn.commit()
        conn.close()

    def save_features(self, symbol, features_dict, regime):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO feature_store (symbol, timestamp, features_json, regime)
            VALUES (?, datetime('now'), ?, ?)
        """, (symbol, json.dumps(features_dict), regime))
        conn.commit()
        conn.close()

# Compatibility helper
def get_db():
    return DatabaseManager()
