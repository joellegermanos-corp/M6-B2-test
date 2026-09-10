from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib

MODEL_FILENAMES = (
    ("pyrenex_risk_v2.joblib", "pyrenex_risk_v2.json"),
    ("pyrenex_risk_v2_1.joblib", "pyrenex_risk_v2_1.json"),
)


def load_model_and_metadata(models_dir: Path) -> tuple[Any, dict]:
    """Load the Pyrenex risk model and its metadata from a models directory."""
    for model_filename, metadata_filename in MODEL_FILENAMES:
        model_path = models_dir / model_filename
        meta_path = models_dir / metadata_filename
        if model_path.exists() and meta_path.exists():
            model = joblib.load(model_path)
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            return model, metadata

    expected = ", ".join(model for model, _ in MODEL_FILENAMES)
    raise FileNotFoundError(f"No model artifact found in {models_dir}; expected one of {expected}")
