from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[3]
SERVICE_MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
ROOT_MODELS_DIR = ROOT_DIR / "models"
MODELS_DIR = ROOT_MODELS_DIR if ROOT_MODELS_DIR.exists() else SERVICE_MODELS_DIR


def _load_model_metadata():
    metadata_path = MODELS_DIR / "pyrenex_risk_v2.json"
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_predict_valid_returns_class_and_proba(client, valid_payload):
    resp = client.post("/predict", json=valid_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["prediction"] in (0, 1)
    assert 0.0 <= body["probability"] <= 1.0

    meta = _load_model_metadata()
    assert body["model_version"] == meta["model_version"]


def test_info_contract_is_respected(client):
    resp = client.get("/info")
    assert resp.status_code == 200

    body = resp.json()
    meta = _load_model_metadata()

    required_keys = {
        "model_name",
        "model_version",
        "metrics_holdout",
        "sklearn_version",
        "dataset_sha256",
    }
    assert required_keys.issubset(body.keys())

    assert body["model_name"] == meta["model_name"]
    assert body["model_version"] == meta["model_version"]
    assert body["metrics_holdout"] == meta["metrics_holdout"]
    assert body["sklearn_version"] == meta["sklearn_version"]
    assert body["dataset_sha256"] == meta["dataset_sha256"]


def test_predict_invalid_returns_422(client, valid_payload):
    bad = dict(valid_payload)
    bad["fico_range_low"] = 9999
    resp = client.post("/predict", json=bad)
    assert resp.status_code == 422


def test_model_contract_features_and_output():
    model = joblib.load(MODELS_DIR / "pyrenex_risk_v2.joblib")
    meta = json.loads((MODELS_DIR / "pyrenex_risk_v2.json").read_text())

    cols = meta["feature_columns_numeric"] + meta["feature_columns_categorical"]
    row = {
        "loan_amnt": 10000.0,
        "int_rate": 13.5,
        "installment": 340.0,
        "annual_inc": 55000.0,
        "dti": 18.2,
        "delinq_2yrs": 0,
        "fico_range_low": 690,
        "revol_util": 42.5,
        "term": "36 months",
        "grade": "B",
        "home_ownership": "MORTGAGE",
        "verification_status": "Not Verified",
        "purpose": "debt_consolidation",
        "emp_length": "10+ years",
    }
    X = pd.DataFrame([row])[cols]
    proba = float(model.predict_proba(X)[0, 1])
    assert 0.0 <= proba <= 1.0
