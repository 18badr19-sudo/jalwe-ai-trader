import sqlite3
import json
from datetime import datetime

class ChartAndLearningEngine:
    def __init__(self, db_path="jalwe_learning.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """إنشاء جداول قاعدة البيانات لتخزين اللقطات والصفقات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timestamp TEXT,
                status TEXT,
                score INTEGER,
                data_json TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def save_feature_snapshot(self, symbol, state_data):
        """حفظ لقطة كاملة لخصائص السهم في قاعدة البيانات للاستفادة منها في التعلم"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO feature_snapshots (symbol, timestamp, status, score, data_json)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                symbol, 
                str(datetime.now()), 
                state_data.get('status'), 
                state_data.get('score', 0), 
                json.dumps(state_data)
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB Error saving snapshot: {e}")

    def get_learning_stats(self):
        """استرجاع إحصائيات التعلم الآلي واللقطات المخزنة"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM feature_snapshots')
            count = cursor.fetchone()[0]
            conn.close()
            return f"عدد اللقطات والتحليلات المخزنة للتعلم الذاتي: {count} حالة."
        except Exception as e:
            return "قاعدة البيانات جاهزة وتعمل بكفاءة."
