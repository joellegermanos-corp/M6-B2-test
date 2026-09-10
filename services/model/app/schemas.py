from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")


class LoanApplication(BaseModel):
    loan_amnt: float
    int_rate: float
    installment: float
    annual_inc: float
    dti: float
    delinq_2yrs: int
    fico_range_low: int = Field(..., ge=300, le=850)
    revol_util: float
    term: str
    grade: str
    home_ownership: str
    verification_status: str
    purpose: str
    emp_length: str


class InfoResponse(BaseModel):
    api_version: str
    model_name: str
    model_version: str
    model_created_at: str
    metrics_holdout: Dict[str, Any]
    sklearn_version: Optional[str] = None
    dataset_sha256: Optional[str] = None


class Prediction(BaseModel):
    prediction: int
    probability: float
    model_version: str
    request_id: str
