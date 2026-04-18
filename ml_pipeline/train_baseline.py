from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier


@dataclass
class TrainingArtifacts:
    model_path: Path
    auc: float


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    X = df[
        [
            "hour_of_day",
            "day_of_week",
            "road_type",
            "weather",
            "crash_density",
            "reports_30d",
            "reports_60d",
            "reports_90d",
            "reporter_weight",
        ]
    ]
    y = df["crash_within_6m"]
    return X, y


def train_model(dataset_path: Path, model_path: Path) -> TrainingArtifacts:
    df = pd.read_csv(dataset_path)
    X, y = build_features(df)

    cat_cols = ["road_type", "weather"]
    num_cols = [c for c in X.columns if c not in cat_cols]
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
            ("num", "passthrough", num_cols),
        ]
    )

    model = XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="auc",
    )

    pipeline = Pipeline([("preprocessor", preprocessor), ("model", model)])
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    pipeline.fit(X_train, y_train)
    preds = pipeline.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, preds)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline.named_steps["model"].save_model(str(model_path))
    return TrainingArtifacts(model_path=model_path, auc=auc)


if __name__ == "__main__":
    artifacts = train_model(
        dataset_path=Path("ml_pipeline/data/baseline_training.csv"),
        model_path=Path("ml_pipeline/models/crash_predictor_v1.json"),
    )
    print({"model_path": str(artifacts.model_path), "auc": round(artifacts.auc, 4)})
