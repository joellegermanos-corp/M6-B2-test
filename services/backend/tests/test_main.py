import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app


VALID_APPLICATION = {
    "loan_amnt": 15000.0,
    "int_rate": 12.5,
    "installment": 350.0,
    "annual_inc": 90000.0,
    "dti": 18.0,
    "delinq_2yrs": 0,
    "fico_range_low": 680,
    "revol_util": 35.0,
    "term": "36 months",
    "grade": "B",
    "home_ownership": "MORTGAGE",
    "verification_status": "Verified",
    "purpose": "debt_consolidation",
    "emp_length": "5 years",
}


def test_score_calls_model_and_returns_prediction(monkeypatch):
    async def fake_post(self, url, json, headers=None):
        assert url.endswith("/predict")
        assert headers["X-Request-ID"]
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "prediction": 1,
                "probability": 0.42,
                "model_version": "v1.2.3",
                "request_id": headers["X-Request-ID"],
            },
            text="ok",
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = TestClient(app)
    response = client.post("/score", json=VALID_APPLICATION, headers={"X-Request-ID": "req-123"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["prediction"] == 1
    assert payload["probability"] == 0.42
    assert payload["request_id"] == "req-123"
