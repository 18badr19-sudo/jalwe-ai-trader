import sqlite3
import json
from datetime import datetime
import numpy as np
from sklearn.ensemble import RandomForestClassifier

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
        """حفظ لقطة الميزات وقت اتخاذ القرار"""
        snapshot_id = None
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
            snapshot_id = cursor.lastrowid
            conn.close()
        except Exception as e:
            print(f"DB Error saving snapshot: {e}")
        return snapshot_id

    def update_trade_outcome(self, symbol, outcome_value):
        """تحديث نتيجة أحدث صفقة لنفس الرمز (1 للربح، 0 للخسارة) لتعلم الذكاء الاصطناعي"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # البحث عن آخر لقطة مفتوحة لهذا الرمز وتحديثها
            cursor.execute('''
                UPDATE feature_snapshots 
                SET outcome = ? 
                WHERE symbol = ? AND outcome = -1 
                ORDER BY id DESC LIMIT 1
            ''', (outcome_value, symbol))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB Error updating outcome: {e}")

    def fetch_training_data(self):
        """جلب البيانات التي تم حسم نتيجتها فقط لتدريب النموذج"""
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
            cursor.execute('SELECT COUNT(*) FROM feature_snapshots WHERE outcome != -1')
            trained_count = cursor.fetchone()[0]
            conn.close()
            return f"Active AI Learning Cases: {trained_count} resolved trades."
        except Exception as e:
            return "Database is active."
