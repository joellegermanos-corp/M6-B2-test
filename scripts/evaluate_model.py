"""Evaluation continue du modele de production sur le jeu de reference."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import f1_score, recall_score, roc_auc_score

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
MODELS = ROOT / "models"
REFERENCE_SET = DATA / "reference_set.csv"
MODEL_PATH = MODELS / "pyrenex_risk_v2.joblib"
METADATA_PATH = MODELS / "pyrenex_risk_v2.json"

THRESHOLDS = {
    "f1_macro": 0.56,
    "recall_default": 0.60,
    "roc_auc": 0.70,
}


def compute_metrics(model, reference: pd.DataFrame, metadata: dict) -> dict[str, float]:
    features = metadata["feature_columns_numeric"] + metadata["feature_columns_categorical"]
    target = metadata["target_column"]
    mapping = metadata["target_mapping"]
    y_true = reference[target].map(mapping).astype(int)
    y_pred = model.predict(reference[features])
    y_proba = model.predict_proba(reference[features])[:, 1]
    return {
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_default": float(recall_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-tag", default="dev")
    parser.add_argument("--degrade", action="store_true")
    args = parser.parse_args()

    model = joblib.load(MODEL_PATH)
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    reference = pd.read_csv(REFERENCE_SET)

    if args.degrade:
        reference = reference.copy()
        reference["loan_status"] = reference["loan_status"].sample(
            frac=1.0, random_state=42
        ).reset_index(drop=True)

    metrics = compute_metrics(model, reference, metadata)
    violations = [
        f"{metric}={metrics[metric]:.4f} < {threshold:.4f}"
        for metric, threshold in THRESHOLDS.items()
        if metrics[metric] < threshold
    ]
    result = {
        "release_tag": args.release_tag,
        "model_version": metadata["model_version"],
        "reference_set": str(REFERENCE_SET.relative_to(ROOT)),
        "n_reference": len(reference),
        "metrics": metrics,
        "violations": violations,
        "status": "failed" if violations else "passed",
    }
    print(json.dumps(result, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
