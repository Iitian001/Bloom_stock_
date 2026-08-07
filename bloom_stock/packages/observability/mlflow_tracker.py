import mlflow
from typing import Dict, Any, Optional, Union
from pathlib import Path
from loguru import logger
from mlflow.entities import Run

class MLFlowTracker:
    """Lightweight wrapper for MLFlow experiment tracking."""
    
    def __init__(self, experiment_name: str, db_uri: str = "sqlite:///mlflow.db"):
        self.experiment_name = experiment_name
        self.db_uri = db_uri
        mlflow.set_tracking_uri(self.db_uri)
        mlflow.set_experiment(self.experiment_name)
        logger.info(f"Initialized MLFlow tracker for experiment: {experiment_name} at {db_uri}")
        
    def start_run(self, run_name: Optional[str] = None) -> Run:
        """Start a new MLflow run."""
        run = mlflow.start_run(run_name=run_name)
        logger.info(f"Started MLFlow run: {run_name} (ID: {run.info.run_id})")
        return run
        
    def log_params(self, params: Dict[str, Any]) -> None:
        """Log parameters to the active MLflow run."""
        mlflow.log_params(params)
        logger.debug(f"Logged {len(params)} parameters to MLFlow")
        
    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        """Log metrics to the active MLflow run."""
        mlflow.log_metrics(metrics, step=step)
        logger.debug(f"Logged {len(metrics)} metrics to MLFlow at step {step}")
        
    def log_artifact(self, local_path: Union[str, Path], artifact_path: Optional[str] = None) -> None:
        """Log an artifact (file or directory) to the active MLflow run."""
        mlflow.log_artifact(str(local_path), artifact_path)
        logger.info(f"Logged artifact {local_path} to MLFlow")
