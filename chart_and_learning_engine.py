"""
chart_and_learning_engine.py
=============================
محرك التعلم الآلي الوحيد والموحّد لـ JALWE V4.

هذا الملف يحل محل ai_engine.py و ml_predictor.py و learning_engine.py
(اللي كانت غير مستخدمة أصلًا بالمشروع — راجع الخلاصة اللي أرسلتها بالمحادثة).

الفكرة:
1. عند فتح صفقة: نخزن "لقطة الميزات" (feature snapshot) وقت اتخاذ القرار.
2. عند إغلاق الصفقة: نسجل النتيجة الفعلية (ربح=1 / خسارة=0).
3. بعد تجمّع عدد كافٍ من الصفقات المغلقة (MIN_SAMPLES_TO_TRAIN)،
   ندرّب RandomForestClassifier حقيقي على البيانات المتجمعة.
4. نستخدم النموذج المدرّب للتنبؤ باحتمالية نجاح أي فرصة جديدة.
5. قبل توفر بيانات كافية → predict_win_probability() ترجع None،
   والنظام (main.py) يعتمد على القواعد فقط تلقائيًا (fallback آمن).

الدوال feed_trade_result() و optimize_models() موجودة هنا خصيصًا
بنفس الأسماء اللي يتوقعها main.py (كان فيه hasattr() يفشل بصمت
لأن الأسماء ما كانت متطابقة — هذا كان سبب تعطّل "التعلم الذاتي" بالكامل).
"""

import os
import json
import sqlite3
from datetime import datetime

import numpy as np

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class ChartAndLearningEngine:

    # ترتيب الميزات ثابت — أي تعديل يتطلب إعادة تدريب كاملة من الصفر
    FEATURE_KEYS = [
        "rvol",
        "compression",              # ATR كنسبة من السعر (تقلب/انضغاط)
        "vwap_reclaimed",           # 1 لو السعر فوق VWAP، وإلا 0
        "distance_to_resistance",   # % بُعد السعر عن أقرب مقاومة
        "volume_speed_high",        # 1 لو تسارع الحجم مرتفع، وإلا 0
    ]

    MIN_SAMPLES_TO_TRAIN = 40
    AUTO_RETRAIN_EVERY_N_NEW_LABELS = 10

    def __init__(self, db_path="jalwe_learning.db", model_path=None):
        self.db_path = db_path
        self.model_path = model_path or os.getenv("JALWE_MODEL_PATH", "jalwe_ml_model.joblib")
        self._model = None
        self._init_db()
        self._load_model_if_exists()

    # ========================================================
    # DB SETUP
    # ========================================================

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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ml_training_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trained_at TEXT,
                samples_used INTEGER,
                cv_accuracy REAL,
                notes TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def _load_model_if_exists(self):
        if not SKLEARN_AVAILABLE:
            return
        if os.path.exists(self.model_path):
            try:
                self._model = joblib.load(self.model_path)
            except Exception:
                self._model = None

    # ========================================================
    # RECORDING (كما كانت، بدون تغيير بالسلوك الأساسي)
    # ========================================================

    def save_feature_snapshot(self, symbol, state_data):
        """حفظ لقطة الميزات وقت اتخاذ القرار (يُستدعى عند فتح صفقة)."""
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
        """تحديث نتيجة أحدث صفقة مفتوحة لنفس الرمز (1 للربح، 0 للخسارة)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
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
        """جلب البيانات التي تم حسم نتيجتها فقط لتدريب النموذج."""
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
                X.append(self._build_vector(data))
                y.append(outcome)
            return X, y
        except Exception:
            return [], []

    def get_learning_stats(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM feature_snapshots WHERE outcome != -1')
            trained_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM feature_snapshots WHERE outcome = -1')
            pending_count = cursor.fetchone()[0]
            conn.close()
            model_state = "جاهز ✅" if self._model is not None else "غير مدرَّب بعد ⏳"
            return (
                f"Active AI Learning Cases: {trained_count} resolved trades "
                f"({pending_count} pending). Model: {model_state}."
            )
        except Exception:
            return "Database is active."

    # ========================================================
    # FEATURE VECTOR BUILDING
    # ========================================================

    def _build_vector(self, data: dict):
        return [
            float(data.get("rvol", 1.0) or 0.0),
            float(data.get("compression", 0.0) or 0.0),
            float(data.get("vwap_reclaimed", 0) or 0),
            float(data.get("distance_to_resistance", 0.01) or 0.0),
            1.0 if (data.get("volume_speed") == "HIGH" or data.get("volume_speed_high")) else 0.0,
        ]

    # ========================================================
    # TRAINING (الجزء اللي كان ناقص كليًا سابقًا)
    # ========================================================

    def train_model(self):
        """
        يدرّب RandomForestClassifier فعليًا على كل الصفقات المغلقة المتوفرة.
        يرجع dict يوضح هل تم التدريب ولماذا لأ لو ما تم.
        """
        if not SKLEARN_AVAILABLE:
            return {
                "trained": False,
                "reason": "مكتبة scikit-learn/joblib غير مثبتة (pip install scikit-learn joblib)"
            }

        X, y = self.fetch_training_data()
        n_samples = len(X)

        if n_samples < self.MIN_SAMPLES_TO_TRAIN:
            return {
                "trained": False,
                "reason": f"عدد العينات غير كافٍ ({n_samples}/{self.MIN_SAMPLES_TO_TRAIN}). "
                          f"النظام يعمل بالقواعد فقط حتى تتوفر بيانات كافية.",
                "samples": n_samples
            }

        if len(set(y)) < 2:
            return {
                "trained": False,
                "reason": "كل الصفقات المسجلة لها نفس النتيجة (كلها ربح أو كلها خسارة) — لا يمكن تدريب مصنّف بعد.",
                "samples": n_samples
            }

        X_arr = np.array(X)
        y_arr = np.array(y)

        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=5,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=42
        )

        cv_accuracy = None
        try:
            folds = min(5, max(2, n_samples // 10))
            scores = cross_val_score(model, X_arr, y_arr, cv=folds)
            cv_accuracy = float(scores.mean())
        except Exception:
            cv_accuracy = None

        model.fit(X_arr, y_arr)

        try:
            joblib.dump(model, self.model_path)
        except Exception as e:
            return {"trained": False, "reason": f"فشل حفظ النموذج: {e}", "samples": n_samples}

        self._model = model

        trained_at = datetime.now().isoformat()
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO ml_training_runs (trained_at, samples_used, cv_accuracy, notes) VALUES (?, ?, ?, ?)",
                (trained_at, n_samples, cv_accuracy, "auto-retrain")
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

        return {
            "trained": True,
            "samples": n_samples,
            "cv_accuracy": cv_accuracy,
            "trained_at": trained_at
        }

    # ========================================================
    # INFERENCE (الجزء الثاني اللي كان ناقص)
    # ========================================================

    def predict_win_probability(self, features: dict):
        """
        يرجع احتمالية النجاح (0.0 - 1.0)، أو None لو النموذج غير جاهز بعد.
        """
        if self._model is None:
            return None
        try:
            vector = np.array([self._build_vector(features)])
            proba = self._model.predict_proba(vector)[0]
            classes = list(self._model.classes_)
            if 1 in classes:
                return float(proba[classes.index(1)])
            return None
        except Exception:
            return None

    def is_model_ready(self):
        return self._model is not None

    def get_last_training_info(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT trained_at, samples_used, cv_accuracy FROM ml_training_runs ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return {"trained_at": row[0], "samples_used": row[1], "cv_accuracy": row[2]}
            return None
        except Exception:
            return None

    # ========================================================
    # COMPATIBILITY LAYER — الأسماء اللي يتوقعها main.py بالضبط
    # ========================================================

    def feed_trade_result(self, symbol, profit_pct, signal_score=None, strategy=None):
        """
        يُستدعى من main.py عند إغلاق كل صفقة.
        (سابقًا هذه الدالة ما كانت موجودة إطلاقًا، فكان hasattr() يفشل بصمت
        ولا يصير أي تعلم فعلي رغم إن الكود يبدو سليم.)
        """
        outcome = 1 if (profit_pct or 0) > 0 else 0
        self.update_trade_outcome(symbol, outcome)

        # إعادة تدريب تلقائية خفيفة كل ما تجمعت دفعة جديدة من النتائج
        try:
            _, y = self.fetch_training_data()
            if len(y) >= self.MIN_SAMPLES_TO_TRAIN and len(y) % self.AUTO_RETRAIN_EVERY_N_NEW_LABELS == 0:
                self.train_model()
        except Exception:
            pass

    def optimize_models(self):
        """
        يُستدعى من main.py عند الضغط على زر "فحص وتحفيز التعلم الذاتي".
        (نفس المشكلة سابقًا — الاسم ما كان مطابقًا فما كان يُستدعى أبدًا.)
        """
        return self.train_model()
