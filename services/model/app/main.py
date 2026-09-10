from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Request, status

try:
    from .model_loader import load_model_and_metadata
    from .schemas import HealthResponse, InfoResponse, LoanApplication, Prediction
except ImportError:  # pragma: no cover - fallback when app is launched as top-level module
    from app.model_loader import load_model_and_metadata
    from app.schemas import HealthResponse, InfoResponse, LoanApplication, Prediction

def _resolve_project_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in (current.parent, *current.parents):
        models = candidate / "models"
        has_promoted = (models / "pyrenex_risk_v2_1.joblib").exists() and (models / "pyrenex_risk_v2_1.json").exists()
        has_production = (models / "pyrenex_risk_v2.joblib").exists() and (models / "pyrenex_risk_v2.json").exists()
        if has_promoted or has_production:
            return candidate
    return current.parent.parent


ROOT_DIR = _resolve_project_root()
SERVICE_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
ROOT_MODELS_DIR = ROOT_DIR / "models"

MODEL_DIR_CANDIDATES = [
    ROOT_MODELS_DIR,
    SERVICE_MODELS_DIR,
]


def _resolve_model_dir() -> Path:
    for candidate in MODEL_DIR_CANDIDATES:
        has_promoted = (candidate / "pyrenex_risk_v2_1.joblib").exists() and (candidate / "pyrenex_risk_v2_1.json").exists()
        has_production = (candidate / "pyrenex_risk_v2.joblib").exists() and (candidate / "pyrenex_risk_v2.json").exists()
        if has_promoted or has_production:
            return candidate
    return ROOT_MODELS_DIR


MODELS_DIR = _resolve_model_dir()
MODEL_PATH = MODELS_DIR / "pyrenex_risk_v2.joblib"
META_PATH = MODELS_DIR / "pyrenex_risk_v2.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    has_promoted = (MODELS_DIR / "pyrenex_risk_v2_1.joblib").exists() and (MODELS_DIR / "pyrenex_risk_v2_1.json").exists()
    has_production = MODEL_PATH.exists() and META_PATH.exists()
    if not has_promoted and not has_production:
        raise RuntimeError(f"Model artifacts missing in {MODELS_DIR}")

    app.state.model, app.state.metadata = load_model_and_metadata(MODELS_DIR)
    yield
    app.state.model = None


app = FastAPI(
    title="Pyrenex Model Service",
    version="2.1.0",
    description="Service de scoring crédit Pyrenex",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    if not hasattr(app.state, "model") or app.state.model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded",
        )
    return HealthResponse(status="ok")


@app.get("/info", response_model=InfoResponse)
async def info() -> InfoResponse:
    meta = app.state.metadata
    return InfoResponse(
        api_version=app.version,
        model_name=meta["model_name"],
        model_version=meta["model_version"],
        model_created_at=meta["created_at"],
        metrics_holdout=meta["metrics_holdout"],
        sklearn_version=meta.get("sklearn_version"),
        dataset_sha256=meta.get("dataset_sha256"),
    )


@app.post("/predict", response_model=Prediction, status_code=status.HTTP_200_OK)
async def predict(application: LoanApplication, request: Request) -> Prediction:
    X = pd.DataFrame([application.model_dump()])
    pred = int(app.state.model.predict(X)[0])
    proba = float(app.state.model.predict_proba(X)[0, 1])

    return Prediction(
        prediction=pred,
        probability=round(proba, 4),
        model_version=app.state.metadata["model_version"],
        request_id=getattr(request.state, "request_id", "n/a"),
    )
