"""Réentraînement automatique (SQUELETTE À COMPLÉTER → scripts/retrain.py).

Déclenché sur un seuil de feedbacks **non consommés**. Réutilise la Pipeline M1
(preprocess.py). Mini-cours : 03 (trigger), 04 (réentraînement + promotion).

⚠️ Deux questions distinctes, à ne jamais confondre :
  - « pourquoi réentraîner ? »  → le TRIGGER (ci-dessous)
  - « pourquoi déployer ? »     → la PROMOTION (scripts/promotion.py)
Un réentraînement déclenché n'implique aucune mise en production.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).parent))
from preprocess import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_MAPPING,
    build_preprocessor,
    load_dataset,
)

# TODO 0 — implémentez decide_promotion() dans scripts/promotion.py, puis :
# from promotion import decide_promotion

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
MODELS = ROOT / "models"
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Le candidat n'est PAS une version officielle tant qu'il n'est pas promu.
CANDIDATE_PATH = MODELS / "pyrenex_risk_candidate.joblib"
PROMOTED_PATH = MODELS / "pyrenex_risk_v2_1.joblib"
PRODUCTION_PATH = MODELS / "pyrenex_risk_v2.joblib"
DECISION_LOG = ROOT / "decisions_log.jsonl"

RF_PARAMS = dict(
    n_estimators=200,
    max_depth=10,
    min_samples_leaf=10,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)


def _load_feedbacks() -> pd.DataFrame:
    """Load the feedbacks from SQLite if available, else from the CSV fixture."""
    db_path = DATA / "feedbacks.db"
    if db_path.exists():
        with sqlite3.connect(db_path) as con:
            return pd.read_sql_query(
                "SELECT request_id, true_label, used_for_training FROM feedbacks",
                con,
            )

    feedbacks = pd.read_csv(DATA / "feedbacks_simules.csv")
    if "used_for_training" not in feedbacks.columns:
        feedbacks["used_for_training"] = 0
    return feedbacks


def _build_training_data(feedbacks: pd.DataFrame) -> pd.DataFrame:
    """Build the training dataset from the original train set + corrected prod rows."""
    train_df = pd.read_csv(DATA / "lending_club_train.csv")
    prod_df = pd.read_csv(DATA / "prod_scored.csv")

    useful = feedbacks.loc[feedbacks["used_for_training"] == 0, ["request_id", "true_label"]].copy()
    corrected = prod_df.merge(useful, on="request_id", how="inner")
    corrected["loan_status"] = corrected["true_label"].map({0: "Fully Paid", 1: "Charged Off"})
    corrected = corrected[train_df.columns]

    training_df = pd.concat([train_df, corrected], ignore_index=True)
    return training_df


def _compute_metrics(y_true: pd.Series, proba: np.ndarray) -> dict[str, float]:
    """Compute the metrics used in the decision gate."""
    y_pred = (proba >= 0.5).astype(int)
    return {
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_default": float(recall_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, proba)),
    }


def _log_decision(candidate_metrics: dict[str, float], production_metrics: dict[str, float], decision: dict) -> None:
    """Append a decision record to the JSONL log."""
    DECISION_LOG.parent.mkdir(exist_ok=True, parents=True)
    with DECISION_LOG.open("a", encoding="utf-8") as f:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "production_metrics": production_metrics,
            "candidate_metrics": candidate_metrics,
            "decision": decision["promote"],
            "reason": decision["reason"],
        }
        f.write(json.dumps(record, sort_keys=True) + "\n")


def _build_metadata(candidate_metrics: dict[str, float], training_df: pd.DataFrame) -> dict:
    """Write a JSON sidecar describing the promoted candidate."""
    production_json = MODELS / "pyrenex_risk_v2.json"
    base = {}
    if production_json.exists():
        with production_json.open("r", encoding="utf-8") as f:
            base = json.load(f)

    dataset_bytes = training_df.to_csv(index=False).encode("utf-8")
    dataset_sha256 = hashlib.sha256(dataset_bytes).hexdigest()
    payload = {
        **base,
        "model_name": "pyrenex_risk_v2",
        "model_version": "v2.1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sklearn_version": __import__("sklearn").__version__,
        "dataset_sha256": dataset_sha256,
        "metrics_holdout": candidate_metrics,
    }
    return payload


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--min-feedback", type=int, default=200)
    args = p.parse_args()

    feedbacks = _load_feedbacks()

    # TODO 1 — GARDE-SEUIL : comptez les feedbacks NON CONSOMMÉS
    #          (used_for_training == 0), PAS le total. Si < seuil → return 0
    #          (skip, ce n'est pas une erreur).
    #          Piège : avec COUNT(*), le cron redéclenche indéfiniment.
    n_new = int((feedbacks["used_for_training"] == 0).sum())
    if n_new < args.min_feedback:
        print(f"Skip retrain: {n_new} new feedbacks < {args.min_feedback}")
        return 0

    # TODO 2 — build_training_data : train initial + lignes prod corrigées
    #          (jointure sur request_id). ⚠️ Le reference_set n'entre JAMAIS
    #          dans l'entraînement : c'est l'arbitre, pas un ingrédient.
    training_df = _build_training_data(feedbacks)

    # TODO 3 — train_candidate : Pipeline(build_preprocessor(),
    #          RandomForestClassifier(**RF_PARAMS)), puis joblib.dump vers
    #          CANDIDATE_PATH. On écrit un CANDIDAT, pas un v2.1.0.
    X_train = training_df[FEATURES]
    y_train = training_df["loan_status"].map(TARGET_MAPPING)
    candidate = Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            ("classifier", RandomForestClassifier(**RF_PARAMS)),
        ]
    )
    candidate.fit(X_train, y_train)
    joblib.dump(candidate, CANDIDATE_PATH, compress=3)

    # TODO 4 — CONTRACT TEST : le candidat sort une proba dans [0,1] sur le
    #          schéma attendu. Si KO → return 1 (vraie erreur technique).
    sample_proba = candidate.predict_proba(X_train.head(10))
    if sample_proba.shape[1] < 2 or not np.isfinite(sample_proba).all():
        raise ValueError("Candidate probability output is invalid")
    if ((sample_proba < 0) | (sample_proba > 1)).any():
        raise ValueError("Candidate probabilities are outside [0, 1]")

    # TODO 5 — evaluate_candidate : mesurez le candidat ET le modèle de
    #          production sur le MÊME reference_set, avec le MÊME code.
    #          Sinon vous comparez deux mesures, pas deux modèles.
    ref_X, ref_y = load_dataset(DATA / "reference_set.csv")
    production_model = joblib.load(PRODUCTION_PATH)
    cand_proba = candidate.predict_proba(ref_X)[:, 1]
    prod_proba = production_model.predict_proba(ref_X)[:, 1]
    candidate_metrics = _compute_metrics(ref_y, cand_proba)
    production_metrics = _compute_metrics(ref_y, prod_proba)

    # TODO 6 — DÉCISION : decide_promotion(candidate_metrics, production_metrics).
    #          Journalisez TOUJOURS la décision dans DECISION_LOG (promue ou
    #          rejetée) : métriques des deux modèles, verdict, raison.
    try:
        from promotion import decide_promotion
    except ImportError:
        def decide_promotion(candidate: dict[str, float], production: dict[str, float]):
            # garde-fou minimal si la politique n'est pas encore codée
            candidate_f1 = candidate.get("f1_macro", 0.0)
            production_f1 = production.get("f1_macro", 0.0)
            candidate_recall = candidate.get("recall_default", 0.0)
            production_recall = production.get("recall_default", 0.0)
            if candidate_f1 < 0.60 or candidate_recall < 0.60:
                return type("Decision", (), {"promote": False, "reason": "plancher de qualité non respecté"})()
            if candidate_f1 < production_f1 - 0.01 or candidate_recall < production_recall - 0.01:
                return type("Decision", (), {"promote": False, "reason": "régression critique sur les métriques clés"})()
            if candidate_f1 <= production_f1 and candidate_recall <= production_recall:
                return type("Decision", (), {"promote": False, "reason": "le candidat n'apporte pas de gain suffisant"})()
            return type("Decision", (), {"promote": True, "reason": "gain suffisant et pas de régression critique"})()

    decision = decide_promotion(candidate_metrics, production_metrics)
    _log_decision(candidate_metrics, production_metrics, {"promote": decision.promote, "reason": decision.reason})

    # TODO 7 — Si PROMOTE : joblib.dump vers PROMOTED_PATH + métadonnées,
    #          (en prod : git tag v2.1.0 + push).
    #          Si REJECT : aucun tag, aucun fichier v2.1.0 — et return 0.
    #          Un rejet est une décision normale, pas un plantage.
    if decision.promote:
        joblib.dump(candidate, PROMOTED_PATH, compress=3)
        metadata = _build_metadata(candidate_metrics, training_df)
        metadata_path = PROMOTED_PATH.with_suffix(".json")
        with metadata_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, sort_keys=True)
        print(f"Promoted candidate: {PROMOTED_PATH}")
        return 0

    print(f"Rejected candidate: {decision.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
