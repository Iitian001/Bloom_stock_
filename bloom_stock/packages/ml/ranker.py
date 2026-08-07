import lightgbm as lgb
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from loguru import logger
from bloom_stock.packages.domain.schemas.signals import StrategyCandidate

class MLRanker:
    """Uses LightGBM LambdaRank to sort candidates by expected cost-adjusted return."""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = lgb.Booster(model_file=model_path) if model_path else None
        
    def rank(self, candidates: List[StrategyCandidate], features: Dict[str, Dict[str, float]]) -> List[StrategyCandidate]:
        """Rank candidates using the pre-trained LambdaRank model.
        
        Args:
            candidates: Generated candidates from strategies
            features: Dictionary mapping instrument_id to their ML feature vector
            
        Returns:
            Sorted list of StrategyCandidates (highest predicted edge first)
        """
        if not self.model or not candidates:
            logger.debug("No model loaded or no candidates provided, returning original candidates.")
            return candidates
            
        try:
            # Build a pandas DataFrame from the features corresponding to the candidates
            feature_list = []
            for candidate in candidates:
                # Fallback to empty dict if features for instrument are missing
                inst_features = features.get(candidate.instrument_id, {})
                feature_list.append(inst_features)
                
            df_features = pd.DataFrame(feature_list)
            
            # Predict scores
            scores = self.model.predict(df_features)
            
            # Sort candidates by score descending
            scored_candidates = list(zip(candidates, scores))
            scored_candidates.sort(key=lambda x: x[1], reverse=True)
            
            return [c for c, s in scored_candidates]
            
        except Exception as e:
            logger.error(f"Error ranking candidates: {e}")
            return candidates
        
    def train(self, X_train: pd.DataFrame, y_train: pd.Series, group_train: np.ndarray, 
              X_val: pd.DataFrame, y_val: pd.Series, group_val: np.ndarray):
        """Train the LambdaRank model."""
        logger.info("Training LightGBM LambdaRank model...")
        
        train_data = lgb.Dataset(X_train, label=y_train, group=group_train)
        val_data = lgb.Dataset(X_val, label=y_val, group=group_val, reference=train_data)
        
        params = {
            'objective': 'lambdarank',
            'metric': 'ndcg',
            'ndcg_eval_at': [1, 3, 5],
            'learning_rate': 0.05,
            'num_leaves': 31,
            'verbose': -1
        }
        
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=100,
            valid_sets=[train_data, val_data]
        )
        logger.info("Model training completed.")
        
    def save(self, path: str):
        """Save the model to the given path."""
        if self.model:
            self.model.save_model(path)
            logger.info(f"Model saved to {path}")
        else:
            logger.warning("No model to save.")
