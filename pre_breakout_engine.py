import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

class PreBreakoutEngine:
    def __init__(self, alpaca_api, learning_engine):
        self.alpaca = alpaca_api
        self.learning_engine = learning_engine
        self.ai_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self._is_trained = False
        self._initial_train()

    def _initial_train(self):
        """التهيئة والتدريب الأولي (بيانات سابقة أو افتراضية)"""
        X_data, y_data = self.learning_engine.fetch_training_data()
        if len(X_data) > 5:
            self.ai_model.fit(np.array(X_data), np.array(y_data))
            self._is_trained = True
        else:
            X_dummy = np.array([
                [3.5, 1, 1, 0.01, 1], [1.2, 0, 0, 0.05, 0],
                [4.2, 1, 1, 0.005, 1], [1.1, 0, 0, 0.08, 0]
            ])
            y_dummy = np.array([1, 0, 1, 0])
            self.ai_model.fit(X_dummy, y_dummy)
            self._is_trained = True

    def update_model_with_real_data(self):
        """إعادة تدريب النموذج بالبيانات الحقيقية والمكتسبة من السوق"""
        X_data, y_data = self.learning_engine.fetch_training_data()
        if len(X_data) >= 5:
            self.ai_model.fit(np.array(X_data), np.array(y_data))
            self._is_trained = True
            print(f"[AI Learning] Model retrained successfully with {len(X_data)} real trade outcomes.")

    def calculate_metrics(self, symbol):
        # ( نفس الكود السابق الخاص بحساب المؤشرات الحية )
        pass

    def evaluate_pre_breakout(self, data):
        features = np.array([[
            data["rvol"], 
            data["compression"], 
            data["vwap_reclaimed"], 
            data["distance_to_resistance"], 
            1 if data["volume_speed"] == "HIGH" else 0
        ]])
        
        probabilities = self.ai_model.predict_proba(features)[0]
        confidence_score = int(probabilities[1] * 100)
        
        status = "WATCH"
        if confidence_score >= 80:
            status = "ENTRY"
        elif confidence_score >= 65:
            status = "CONFIRMED"
        elif confidence_score >= 50:
            status = "SETUP"
            
        reasons = []
        if data["rvol"] > 2.0:
            reasons.append("Volume acceleration & high RVOL")
        if data["compression"] == 1:
            reasons.append("Price compression near resistance")
        if data["vwap_reclaimed"] == 1:
            reasons.append("VWAP reclaimed")
            
        return {
            "score": confidence_score,
            "status": status,
            "reasons": reasons
        }
