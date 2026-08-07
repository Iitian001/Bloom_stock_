import xgboost as xgb
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit
import joblib
from loguru import logger

from bloom_stock.packages.domain.schemas.signals import StrategyCandidate, MetaLabelResult
from bloom_stock.packages.domain.schemas.regime import RegimeClassification

class MetaLabeler:
    """Uses XGBoost + CalibratedClassifierCV to output exact probability of a successful trade."""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model: Optional[CalibratedClassifierCV] = joblib.load(model_path) if model_path else None
        
    def predict(self, candidate: StrategyCandidate, feature_vector: Dict[str, float]) -> MetaLabelResult:
        """Predict probability of hitting PROFIT barrier before STOP."""
        if not self.model:
            logger.debug("No model loaded. Defaulting take_probability to 1.0.")
            return MetaLabelResult(
                take_probability=1.0,
                calibrated=False,
                uncertainty=0.0,
                model_version="default_v0"
            )
            
        try:
            # Convert feature_vector to DataFrame row
            df_features = pd.DataFrame([feature_vector])
            
            # Predict probability of Class 1 (success)
            # predict_proba returns array of shape (n_samples, n_classes)
            prob = self.model.predict_proba(df_features)[0, 1]
            
            return MetaLabelResult(
                take_probability=prob,
                calibrated=True,
                uncertainty=0.0,  # Placeholder for an uncertainty estimation mechanism
                model_version="xgb_calibrated_v1"
            )
            
        except Exception as e:
            logger.error(f"Error predicting meta-label: {e}")
            return MetaLabelResult(
                take_probability=1.0,
                calibrated=False,
                uncertainty=1.0,
                model_version="error_fallback"
            )
        
    def train(self, X_train: pd.DataFrame, y_train: pd.Series):
        """Train XGBoost classifier and wrap in CalibratedClassifierCV."""
        logger.info("Training MetaLabeler with CalibratedClassifierCV...")
        
        xgb_model = xgb.XGBClassifier(
            objective='binary:logistic',
            eval_metric='logloss',
            use_label_encoder=False
        )
        
        tscv = TimeSeriesSplit(n_splits=5)
        
        self.model = CalibratedClassifierCV(
            estimator=xgb_model,
            cv=tscv,
            method='isotonic'
        )
        
        self.model.fit(X_train, y_train)
        logger.info("MetaLabeler training completed.")
        
    def save(self, path: str):
        """Save the calibrated model to the given path."""
        if self.model:
            joblib.dump(self.model, path)
            logger.info(f"Model saved to {path}")
        else:
            logger.warning("No model to save.")
