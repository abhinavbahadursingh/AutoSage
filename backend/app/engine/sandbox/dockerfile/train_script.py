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
import inspect
import warnings
import traceback
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import joblib

# ML libraries
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    mean_squared_error,
    r2_score,
    mean_absolute_error,
)
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
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


def resolve_target_column(df: pd.DataFrame, target_column: str) -> str:
    """Resolve the target column, tolerating case/whitespace differences.

    Requests spell the target from the UI (``churn``) while the uploaded CSV
    often uses its own casing (``Churn``); an exact match always wins.
    """
    if target_column in df.columns:
        return target_column
    wanted = str(target_column or "").strip().lower()
    for column in df.columns:
        if str(column).strip().lower() == wanted:
            return column
    raise ValueError(
        f"Target column '{target_column}' not found in dataset "
        f"(available: {list(df.columns)[:10]})"
    )


def prepare_data(
    df: pd.DataFrame,
    target_column: str,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple:
    """Split features/target and train/test."""
    target_column = resolve_target_column(df, target_column)
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
        # Dense one-hot so the matrix stays numeric for every estimator below.
        # Without this, string categories cannot be fitted at all.
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
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


def _build(estimator, params: dict, **defaults: Any):
    """Instantiate ``estimator`` with ``params`` over ``defaults``.

    ``params`` comes from the model selector (LLM-authored), so it may already
    carry ``random_state``/``n_jobs``; letting it win avoids a duplicate-kwarg
    TypeError that would silently fail the whole family.
    """
    kwargs = dict(defaults)
    kwargs.update(params)
    return estimator(**kwargs)


def get_model(model_family: str, params: dict, task_type: str):
    """Instantiate model based on family and task type."""
    is_classification = task_type == "classification"

    if model_family == "random_forest":
        if is_classification:
            return _build(RandomForestClassifier, params, random_state=42, n_jobs=1)
        return _build(RandomForestRegressor, params, random_state=42, n_jobs=1)

    elif model_family == "gradient_boosting":
        if is_classification:
            return _build(GradientBoostingClassifier, params, random_state=42)
        return _build(GradientBoostingRegressor, params, random_state=42)

    elif model_family == "hist_gradient_boosting":
        if is_classification:
            return _build(HistGradientBoostingClassifier, params, random_state=42)
        return _build(HistGradientBoostingRegressor, params, random_state=42)

    elif model_family == "logistic_regression":
        if not is_classification:
            raise ValueError("LogisticRegression only for classification")
        return _build(
            LogisticRegression, params, random_state=42, max_iter=1000, n_jobs=1
        )

    elif model_family == "ridge":
        if is_classification:
            raise ValueError("Ridge only for regression")
        return _build(Ridge, params, random_state=42)

    elif model_family == "linear_regression":
        if is_classification:
            raise ValueError("LinearRegression only for regression")
        return _build(LinearRegression, params)

    elif model_family == "svm":
        if is_classification:
            return _build(SVC, params, random_state=42, probability=True)
        return _build(SVR, params)

    elif model_family == "xgboost":
        if not HAS_XGBOOST:
            raise ImportError("XGBoost not installed")
        if is_classification:
            return _build(
                xgb.XGBClassifier, params, random_state=42, n_jobs=1, verbosity=0
            )
        return _build(
            xgb.XGBRegressor, params, random_state=42, n_jobs=1, verbosity=0
        )

    elif model_family == "lightgbm":
        if not HAS_LIGHTGBM:
            raise ImportError("LightGBM not installed")
        if is_classification:
            return _build(
                lgb.LGBMClassifier, params, random_state=42, n_jobs=1, verbosity=-1
            )
        return _build(lgb.LGBMRegressor, params, random_state=42, n_jobs=1, verbosity=-1)

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
    """Compute evaluation metrics.

    Classification always reports accuracy, precision, recall and F1 for the
    positive class (``f1`` is an alias of ``f1_macro``) so any requested
    objective -- not just accuracy -- can be read off the same dict. Macro /
    weighted F1 and ROC AUC are reported alongside when available.
    """
    if task_type == "classification":
        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
            "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        }
        classes = np.unique(y_true)
        # Binary metrics are reported against the positive class (label 1);
        # for multi-class problems macro averages keep them comparable.
        average = "binary" if len(classes) <= 2 else "macro"
        binary_kwargs = {"average": average, "zero_division": 0}
        if average == "binary":
            binary_kwargs["pos_label"] = 1
        metrics["precision"] = float(precision_score(y_true, y_pred, **binary_kwargs))
        metrics["recall"] = float(recall_score(y_true, y_pred, **binary_kwargs))
        # Canonical alias so a request for "f1" resolves without a mapping table.
        metrics["f1"] = metrics["f1_macro"]
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


def metric_score(metrics: dict, metric: str):
    """Read ``metric`` out of a measured metrics dict (alias aware)."""
    name = str(metric or "").strip().lower()
    keys = {
        "f1": ("f1", "f1_macro", "f1_weighted"),
        "f1_macro": ("f1_macro", "f1", "f1_weighted"),
        "f1_weighted": ("f1_weighted", "f1", "f1_macro"),
    }.get(name, (name,))
    for key in keys:
        if key in metrics and metrics[key] is not None:
            try:
                return float(metrics[key])
            except (TypeError, ValueError):
                continue
    return None


def _higher_is_better(metric: str) -> bool:
    return str(metric or "").strip().lower() not in {"mse", "mae", "rmse", "log_loss"}


def _select_best(entries: list, metric: str):
    """Pick the entry with the best ``score`` for ``metric`` (first wins ties)."""
    scored = [e for e in entries if e.get("score") is not None]
    if not scored:
        return None
    reverse = _higher_is_better(metric)
    best = scored[0]
    for entry in scored[1:]:
        better = entry["score"] > best["score"] if reverse else entry["score"] < best["score"]
        if better:
            best = entry
    return best


def _predict_scores(model, X_test):
    """Return hard predictions and (when available) positive-class scores."""
    y_pred = model.predict(X_test)
    y_proba = None
    if hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba(X_test)
            y_proba = proba[:, 1] if proba.ndim == 2 and proba.shape[1] == 2 else proba
        except Exception:
            y_proba = None
    return y_pred, y_proba


def sanitize_params(model_family: str, params: dict, task_type: str) -> dict:
    """Drop hyperparameters the chosen family does not accept.

    A shortlist shares one proposal, and an LLM-proposed param set can name
    keys that only exist on a different estimator. Filtering keeps a mismatch
    from turning into a failed candidate instead of a measured comparison.
    """
    params = dict(params or {})
    try:
        probe = get_model(model_family, {}, task_type)
        target = probe.model if hasattr(probe, "model") else probe  # PyTorchMLP wrapper
        accepted = set(inspect.signature(type(target).__init__).parameters) - {"self"}
        return {k: v for k, v in params.items() if k in accepted}
    except Exception:
        return params


def _fit_and_score(model_family, params, task_type, prepared):
    """Fit one candidate and return its metrics (raises on failure)."""
    X_train, X_test, y_train, y_test, preprocessor, target_encoder = prepared
    model = get_model(model_family, sanitize_params(model_family, params, task_type), task_type)
    model.fit(X_train, y_train)
    y_pred, y_score = _predict_scores(model, X_test)
    metrics = compute_metrics(y_test, y_pred, y_score, task_type)
    return model, metrics, (preprocessor, target_encoder)


def baseline_metrics(y_test, task_type="classification") -> dict:
    """Majority-class baseline metrics, for the baseline-dominance gate."""
    classes, counts = np.unique(y_test, return_counts=True)
    majority = classes[int(np.argmax(counts))]
    y_pred = np.full_like(y_test, majority, dtype=y_test.dtype)
    return compute_metrics(y_test, y_pred, None, task_type)


def run_model_comparison(
    *,
    candidates: list,
    primary_metric: str,
    params: dict,
    task_type: str,
    df,
    target_column: str,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Train and score every candidate, then select on ``primary_metric``.

    Returns the canonical comparison payload::

        {
          "primary_metric", "primary_score", "metrics", "model_comparison",
          "selected_model", "baseline", "models_evaluated", "failures", ...
        }

    Selection uses the requested objective only -- accuracy is reported as a
    secondary metric and never drives the choice.
    """
    target_column = resolve_target_column(df, target_column)
    prepared = prepare_data(df, target_column, test_size=test_size, random_state=random_state)
    _, _, _, y_test, _, _ = prepared

    base = baseline_metrics(y_test, task_type)
    base_score = metric_score(base, primary_metric)

    comparison = []
    failures = {}
    best_model = None
    best_bundle = None

    for family in candidates:
        try:
            model, metrics, bundle = _fit_and_score(family, params, task_type, prepared)
        except Exception as exc:  # noqa: BLE001 - one bad family must not kill the run
            failures[family] = f"{type(exc).__name__}: {exc}"
            print(f"MODEL_FAILED {family}: {type(exc).__name__}: {exc}", flush=True)
            continue
        score = metric_score(metrics, primary_metric)
        comparison.append(
            {
                "model": family,
                "params": dict(params or {}),
                "score": score,
                "primary_metric": primary_metric,
                "metrics": metrics,
                "error": None,
            }
        )
        print(
            f"MODEL_EVALUATED {family} {primary_metric}={score} "
            f"accuracy={metrics.get('accuracy')} precision={metrics.get('precision')} "
            f"recall={metrics.get('recall')} f1={metrics.get('f1')}",
            flush=True,
        )
        if best_model is None:
            best_model, best_bundle = model, bundle

    best = _select_best(comparison, primary_metric)
    selected_model = best["model"] if best else None
    selected_metrics = dict(best["metrics"]) if best else {}
    primary_score = best["score"] if best else None

    return {
        "primary_metric": primary_metric,
        "primary_score": primary_score,
        "metrics": selected_metrics,
        "model_comparison": comparison,
        "selected_model": selected_model,
        "baseline": {
            "model": "majority_class",
            "metrics": base,
            "score": base_score,
            "primary_metric": primary_metric,
        },
        "models_evaluated": len(comparison),
        "models_requested": len(list(candidates)),
        "failures": failures,
        "validation_strategy": "holdout",
        "task_type": task_type,
        "target_column": target_column,
        "n_rows": int(len(df)),
        "n_features": int(prepared[0].shape[1]),
        "test_size": test_size,
        "random_state": random_state,
        "_model": best_model,
        "_bundle": best_bundle,
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


def _resolve_candidates() -> list:
    """Candidate families for compare mode (``CANDIDATE_MODELS`` env, JSON list)."""
    raw = os.environ.get("CANDIDATE_MODELS", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(f) for f in parsed if str(f).strip()]
            if isinstance(parsed, str) and parsed.strip():
                return [parsed.strip()]
        except json.JSONDecodeError:
            return [f.strip() for f in raw.split(",") if f.strip()]
    return [os.environ.get("MODEL_FAMILY", "gradient_boosting")]


def _env_flag(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def main():
    """Main training entry point.

    Two modes, both driven by the *requested* objective:

    - compare mode (``COMPARE_MODELS=1``): trains every candidate family,
      scores each on the requested ``METRIC``, and selects the winner on that
      metric alone.
    - single-model mode: trains ``MODEL_FAMILY`` and reports the full metric set.
    """
    # Read configuration from environment
    model_family = os.environ.get("MODEL_FAMILY", "gradient_boosting")
    metric = os.environ.get("METRIC", "accuracy")
    dataset_name = os.environ.get("DATASET_NAME", "dataset.csv")
    params_json = os.environ.get("MODEL_PARAMS", "{}")
    target_column = os.environ.get("TARGET_COLUMN", "target")
    task_type = os.environ.get("TASK_TYPE", "classification")
    mlflow_run_id = os.environ.get("MLFLOW_RUN_ID", "")
    compare_models = _env_flag("COMPARE_MODELS")

    try:
        params = json.loads(params_json)
    except json.JSONDecodeError:
        params = {}

    # Initialize MLflow (Phase 11)
    mlflow_active = _init_mlflow()
    if mlflow_active and mlflow_run_id:
        # Join existing run from parent process
        mlflow.start_run(run_id=mlflow_run_id)

    workspace = Path(os.environ.get("WORKSPACE_DIR", "/workspace"))
    dataset_path = Path(os.environ.get("DATASET_PATH", str(workspace / "dataset.csv")))

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found at {dataset_path}")

    # Load and prepare data
    df = load_dataset(dataset_path)

    if compare_models:
        comparison = run_model_comparison(
            candidates=_resolve_candidates(),
            primary_metric=metric,
            params=params,
            task_type=task_type,
            df=df,
            target_column=target_column,
            test_size=float(os.environ.get("TEST_SIZE", "0.2")),
            random_state=int(os.environ.get("RANDOM_STATE", "42")),
        )
        metrics = dict(comparison["metrics"])
        model = comparison.pop("_model", None)
        bundle = comparison.pop("_bundle", None)
        preprocessor, target_encoder = bundle if bundle else (None, None)

        if mlflow_active and mlflow.active_run():
            _log_to_mlflow(
                model=model,
                model_family=str(comparison.get("selected_model") or model_family),
                params={**params, "primary_metric": metric},
                metrics=metrics,
                task_type=task_type,
                dataset_name=dataset_name,
                target_column=target_column,
                preprocessor=preprocessor,
                target_encoder=target_encoder,
                model_path=workspace / "model.joblib",
                run_id=mlflow_run_id,
            )

        if model is not None:
            joblib.dump(
                {"model": model, "preprocessor": preprocessor, "target_encoder": target_encoder},
                workspace / "model.joblib",
            )

        (workspace / "metrics.json").write_text(json.dumps(comparison, indent=2, default=str))

        print(f"Models evaluated: {comparison.get('models_evaluated')}")
        print(
            f"Selected model: {comparison.get('selected_model')} "
            f"({metric}={comparison.get('primary_score')})"
        )
        print(f"All metrics: {json.dumps(metrics, default=str)}")

        if mlflow_active and mlflow.active_run():
            mlflow.end_run()
        return

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


def execute_locally(
    *,
    dataset_path: str,
    target_column: str,
    task_type: str = "classification",
    candidates: Optional[list] = None,
    primary_metric: str = "accuracy",
    params: Optional[dict] = None,
    artifact_dir: Optional[str] = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Run the same training in-process (used when Docker is unavailable).

    Returns the canonical comparison payload with the fitted artifacts
    stripped, so the result is JSON-safe for the workflow state.
    """
    df = load_dataset(dataset_path)
    families = list(candidates) if candidates else ["gradient_boosting"]
    result = run_model_comparison(
        candidates=families,
        primary_metric=primary_metric,
        params=dict(params or {}),
        task_type=task_type,
        df=df,
        target_column=target_column,
        test_size=test_size,
        random_state=random_state,
    )

    model = result.pop("_model", None)
    bundle = result.pop("_bundle", None)
    artifacts = []
    if artifact_dir and model is not None:
        out = Path(artifact_dir)
        out.mkdir(parents=True, exist_ok=True)
        preprocessor, target_encoder = bundle if bundle else (None, None)
        path = out / "model.joblib"
        joblib.dump(
            {"model": model, "preprocessor": preprocessor, "target_encoder": target_encoder},
            path,
        )
        artifacts.append(path.name)

    result["artifacts"] = artifacts
    result["dataset_name"] = Path(dataset_path).name
    return result



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