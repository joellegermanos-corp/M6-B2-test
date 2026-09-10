from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib

MODEL_FILENAME = "pyrenex_risk_v2.joblib"
METADATA_FILENAME = "pyrenex_risk_v2.json"


def load_model_and_metadata(models_dir: Path) -> tuple[Any, dict]:
    """Load the Pyrenex risk model and its metadata from a models directory."""
    model_path = models_dir / MODEL_FILENAME
    meta_path = models_dir / METADATA_FILENAME

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found at {model_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"Metadata file not found at {meta_path}")

    model = joblib.load(model_path)
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    return model, metadata
