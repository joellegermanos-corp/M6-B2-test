from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.model.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def valid_payload():
    return {
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