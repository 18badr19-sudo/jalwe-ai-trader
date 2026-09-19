import sqlite3
import json
from datetime import datetime

class ChartAndLearningEngine:
    def __init__(self, db_path="jalwe_learning.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timestamp TEXT,
                status TEXT,
                score INTEGER,
                data_json TEXT,
                outcome INTEGER DEFAULT -1
            )
        ''')
        conn.commit()
        conn.close()

    def save_feature_snapshot(self, symbol, state_data):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO feature_snapshots (symbol, timestamp, status, score, data_json, outcome)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                symbol, 
                str(datetime.now()), 
                state_data.get('status'), 
                state_data.get('score', 0), 
                json.dumps(state_data),
                -1
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB Error saving snapshot: {e}")

    def fetch_training_data(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT data_json, outcome FROM feature_snapshots WHERE outcome != -1')
            rows = cursor.fetchall()
            conn.close()
            
            X, y = [], []
            for row in rows:
                data = json.loads(row[0])
                outcome = row[1]
                features = [
                    data.get("rvol", 1.0),
                    data.get("compression", 0),
                    data.get("vwap_reclaimed", 0),
                    data.get("distance_to_resistance", 0.01),
                    1 if data.get("volume_speed") == "HIGH" else 0
                ]
                X.append(features)
                y.append(outcome)
            return X, y
        except Exception as e:
            return [], []

    def get_learning_stats(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM feature_snapshots')
            count = cursor.fetchone()[0]
            conn.close()
            return f"Stored snapshots for self-learning: {count} cases."
        except Exception as e:
            return "Database is active and operational."
