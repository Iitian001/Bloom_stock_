import polars as pl
from pathlib import Path
from loguru import logger
from typing import List, Dict, Any

class DatasetGenerator:
    """Generates and manages ML datasets (features + labels)."""
    
    def __init__(self, data_dir: Path | str = 'data/ml'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def save_snapshot(self, features: List[Dict[str, Any]], labels: List[Dict[str, Any]], name: str) -> str:
        """Join features and labels, save as Parquet, return file path."""
        if len(features) != len(labels):
            raise ValueError(f"Features ({len(features)}) and labels ({len(labels)}) length mismatch")
            
        df_features = pl.DataFrame(features)
        df_labels = pl.DataFrame(labels)
        
        # Horizontal concatenation assuming 1-to-1 mapping and ordered
        df = pl.concat([df_features, df_labels], how="horizontal")
        
        file_path = self.data_dir / f"{name}.parquet"
        df.write_parquet(file_path)
        logger.info(f"Saved dataset snapshot to {file_path}")
        
        return str(file_path)
        
    def load_snapshot(self, name: str) -> pl.DataFrame:
        """Load a saved dataset snapshot by name."""
        file_path = self.data_dir / f"{name}.parquet"
        if not file_path.exists():
            raise FileNotFoundError(f"Snapshot not found at {file_path}")
        
        df = pl.read_parquet(file_path)
        logger.info(f"Loaded dataset snapshot from {file_path}")
        return df
