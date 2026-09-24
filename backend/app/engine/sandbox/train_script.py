"""Training script template for sandbox execution (Phase 10/11).

This script runs inside the isolated Docker container. It:
1. Loads the dataset from /workspace/dataset.csv
2. Trains a model based on model_family and params
3. Evaluates on a holdout split
4. Logs parameters, metrics, model, and artifacts to MLflow
5. Writes metrics.json and model artifacts to /workspace for sandbox collection

The script is injected with job parameters via environment variables.
MLflow tracking is configured via MLFLOW_TRACKING_URI and MLFLOW_EXPERIMENT_NAME.
"""
import os
import json
import warnings
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import joblib

# ML libraries
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    roc_auc_score,
    mean_squared_error,
    r2_score,
    mean_absolute_error,
)
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    RandomForestClassifier,
    RandomForestRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge, LinearRegression
from sklearn.svm import SVC, SVR

warnings.filterwarnings("ignore")

# Optional imports
try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# MLflow integration (Phase 11)
MLFLOW_ENABLED = False
try:
    import mlflow
    import mlflow.sklearn
    MLFLOW_ENABLED = True
except ImportError:
    pass


def _init_mlflow():
    """Initialize MLflow from environment variables."""
    if not MLFLOW_ENABLED:
        return False

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "autosage_default")

    if not tracking_uri:
        return False

    try:
        mlflow.set_tracking_uri(tracking_uri)
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment is None:
            mlflow.create_experiment(experiment_name)
        else:
            mlflow.set_experiment(experiment_name)
        return True
    except Exception as e:
        print(f"MLflow initialization warning: {e}")
        return False


def load_dataset(path: str) -> pd.DataFrame:
    """Load dataset from CSV."""
    return pd.read_csv(path)


def prepare_data(
    df: pd.DataFrame,
    target_column: str,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple:
    """Split features/target and train/test."""
    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in dataset")

    y = df[target_column]
    X = df.drop(columns=[target_column])

    # Handle categorical target
    if y.dtype == "object" or y.dtype.name == "category":
        le = LabelEncoder()
        y = le.fit_transform(y)
        target_encoder = le
    else:
        target_encoder = None

    # Identify column types
    numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = X.select_dtypes(exclude=[np.number]).columns.tolist()

    # Preprocessing
    numeric_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
    ])

    preprocessor = ColumnTransformer([
        ("num", numeric_transformer, numeric_cols),
        ("cat", categorical_transformer, categorical_cols),
    ])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state,
        stratify=y if len(np.unique(y)) < 50 else None
    )

    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)

    return X_train_proc, X_test_proc, y_train, y_test, preprocessor, target_encoder


def get_model(model_family: str, params: dict, task_type: str):
    """Instantiate model based on family and task type."""
    is_classification = task_type == "classification"

    if model_family == "random_forest":
        if is_classification:
            return RandomForestClassifier(**params, random_state=42, n_jobs=1)
        return RandomForestRegressor(**params, random_state=42, n_jobs=1)

    elif model_family == "gradient_boosting":
        if is_classification:
            return GradientBoostingClassifier(**params, random_state=42)
        return GradientBoostingRegressor(**params, random_state=42)

    elif model_family == "hist_gradient_boosting":
        if is_classification:
            return HistGradientBoostingClassifier(**params, random_state=42)
        return HistGradientBoostingRegressor(**params, random_state=42)

    elif model_family == "logistic_regression":
        if not is_classification:
            raise ValueError("LogisticRegression only for classification")
        return LogisticRegression(**params, random_state=42, max_iter=1000, n_jobs=1)

    elif model_family == "ridge":
        if is_classification:
            raise ValueError("Ridge only for regression")
        return Ridge(**params, random_state=42)

    elif model_family == "linear_regression":
        if is_classification:
            raise ValueError("LinearRegression only for regression")
        return LinearRegression(**params)

    elif model_family == "svm":
        if is_classification:
            return SVC(**params, random_state=42, probability=True)
        return SVR(**params)

    elif model_family == "xgboost":
        if not HAS_XGBOOST:
            raise ImportError("XGBoost not installed")
        if is_classification:
            return xgb.XGBClassifier(**params, random_state=42, n_jobs=1, verbosity=0)
        return xgb.XGBRegressor(**params, random_state=42, n_jobs=1, verbosity=0)

    elif model_family == "lightgbm":
        if not HAS_LIGHTGBM:
            raise ImportError("LightGBM not installed")
        if is_classification:
            return lgb.LGBMClassifier(**params, random_state=42, n_jobs=1, verbosity=-1)
        return lgb.LGBMRegressor(**params, random_state=42, n_jobs=1, verbosity=-1)

    elif model_family == "pytorch_mlp":
        if not HAS_TORCH:
            raise ImportError("PyTorch not installed")
        return PyTorchMLP(params, is_classification)

    else:
        raise ValueError(f"Unknown model family: {model_family}")


class PyTorchMLP:
    """Simple PyTorch MLP wrapper compatible with sklearn interface."""

    def __init__(self, params: dict, is_classification: bool):
        self.params = params
        self.is_classification = is_classification
        self.model = None
        self.device = torch.device("cpu")
        self.epochs = params.get("epochs", 50)
        self.batch_size = params.get("batch_size", 32)
        self.lr = params.get("lr", 0.001)
        self.hidden_sizes = params.get("hidden_sizes", [64, 32])

    def _build_model(self, input_dim: int, output_dim: int):
        layers = []
        prev = input_dim
        for h in self.hidden_sizes:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            prev = h
        layers.append(nn.Linear(prev, output_dim))
        if self.is_classification and output_dim == 1:
            layers.append(nn.Sigmoid())
        elif self.is_classification:
            layers.append(nn.LogSoftmax(dim=1))
        self.model = nn.Sequential(*layers).to(self.device)

    def fit(self, X, y):
        X_tensor = torch.FloatTensor(X).to(self.device)
        if self.is_classification:
            y_tensor = torch.LongTensor(y).to(self.device)
            criterion = nn.CrossEntropyLoss()
            output_dim = len(np.unique(y))
        else:
            y_tensor = torch.FloatTensor(y).unsqueeze(1).to(self.device)
            criterion = nn.MSELoss()
            output_dim = 1

        self._build_model(X.shape[1], output_dim)
        optimizer = optim.Adam(self.model.parameters(), lr=self.lr)

        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        self.model.train()
        for _ in range(self.epochs):
            for xb, yb in loader:
                optimizer.zero_grad()
                pred = self.model(xb)
                loss = criterion(pred, yb)
                loss.backward()
                optimizer.step()

        return self

    def predict(self, X):
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            pred = self.model(X_tensor)
            if self.is_classification:
                if pred.shape[1] == 1:
                    return (pred.cpu().numpy() > 0.5).astype(int).flatten()
                return pred.argmax(dim=1).cpu().numpy()
            return pred.cpu().numpy().flatten()

    def predict_proba(self, X):
        if not self.is_classification:
            raise ValueError("predict_proba only for classification")
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            pred = self.model(X_tensor)
            if pred.shape[1] == 1:
                probs = pred.cpu().numpy().flatten()
                return np.column_stack([1 - probs, probs])
            return torch.exp(pred).cpu().numpy()


def compute_metrics(y_true, y_pred, y_proba=None, task_type="classification") -> dict:
    """Compute evaluation metrics."""
    if task_type == "classification":
        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
            "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        }
        if y_proba is not None:
            try:
                if y_proba.shape[1] == 2:
                    metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba[:, 1]))
                else:
                    metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba, multi_class="ovr"))
            except Exception:
                pass
        return metrics
    else:
        return {
            "mse": float(mean_squared_error(y_true, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "mae": float(mean_absolute_error(y_true, y_pred)),
            "r2": float(r2_score(y_true, y_pred)),
        }


def _log_to_mlflow(
    model: Any,
    model_family: str,
    params: dict,
    metrics: dict,
    task_type: str,
    dataset_name: str,
    target_column: str,
    preprocessor: Any,
    target_encoder: Any,
    model_path: Path,
    run_id: str,
) -> None:
    """Log model, parameters, metrics, and artifacts to MLflow."""
    if not MLFLOW_ENABLED:
        return

    try:
        # Log parameters
        mlflow.log_params({
            "model_family": model_family,
            "task_type": task_type,
            "dataset_name": dataset_name,
            "target_column": target_column,
            **params,
        })

        # Log metrics
        mlflow.log_metrics(metrics)

        # Log model
        mlflow.sklearn.log_model(
            sk_model={"model": model, "preprocessor": preprocessor, "target_encoder": target_encoder},
            artifact_path="model",
            registered_model_name=None,
        )

        # Log dataset info as tags
        mlflow.set_tags({
            "dataset_name": dataset_name,
            "target_column": target_column,
            "task_type": task_type,
            "model_family": model_family,
            "autosage_run_id": run_id,
        })

    except Exception as e:
        print(f"MLflow logging warning: {e}")


def main():
    """Main training entry point."""
    # Read configuration from environment
    model_family = os.environ.get("MODEL_FAMILY", "gradient_boosting")
    metric = os.environ.get("METRIC", "accuracy")
    dataset_name = os.environ.get("DATASET_NAME", "dataset.csv")
    params_json = os.environ.get("MODEL_PARAMS", "{}")
    target_column = os.environ.get("TARGET_COLUMN", "target")
    task_type = os.environ.get("TASK_TYPE", "classification")
    mlflow_run_id = os.environ.get("MLFLOW_RUN_ID", "")

    try:
        params = json.loads(params_json)
    except json.JSONDecodeError:
        params = {}

    # Initialize MLflow (Phase 11)
    mlflow_active = _init_mlflow()
    if mlflow_active and mlflow_run_id:
        # Join existing run from parent process
        mlflow.start_run(run_id=mlflow_run_id)

    workspace = Path("/workspace")
    dataset_path = workspace / "dataset.csv"

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found at {dataset_path}")

    # Load and prepare data
    df = load_dataset(dataset_path)
    X_train, X_test, y_train, y_test, preprocessor, target_encoder = prepare_data(
        df, target_column
    )

    # Train model
    model = get_model(model_family, params, task_type)
    model.fit(X_train, y_train)

    # Predict
    y_pred = model.predict(X_test)
    y_proba = None
    if hasattr(model, "predict_proba"):
        try:
            y_proba = model.predict_proba(X_test)
        except Exception:
            pass

    # Compute metrics
    metrics = compute_metrics(y_test, y_pred, y_proba, task_type)

    # Log to MLflow (Phase 11)
    if mlflow_active and mlflow.active_run():
        _log_to_mlflow(
            model=model,
            model_family=model_family,
            params=params,
            metrics=metrics,
            task_type=task_type,
            dataset_name=dataset_name,
            target_column=target_column,
            preprocessor=preprocessor,
            target_encoder=target_encoder,
            model_path=workspace / "model.joblib",
            run_id=mlflow_run_id,
        )

    # Save model artifact locally (for sandbox collection)
    model_path = workspace / "model.joblib"
    joblib.dump(
        {"model": model, "preprocessor": preprocessor, "target_encoder": target_encoder},
        model_path
    )

    # Save metrics locally (for sandbox collection)
    metrics_path = workspace / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))

    # Print summary to stdout
    print(f"Training completed: {model_family}")
    print(f"Metric ({metric}): {metrics.get(metric, 'N/A')}")
    print(f"All metrics: {json.dumps(metrics)}")

    # End MLflow run if we started it
    if mlflow_active and mlflow.active_run():
        mlflow.end_run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        traceback.print_exc()
        # End MLflow run with FAILED status if active
        if MLFLOW_ENABLED and mlflow.active_run():
            mlflow.end_run(status="FAILED")
        exit(1)