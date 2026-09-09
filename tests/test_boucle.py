"""Tests de la boucle — verts sur le squelette, plus exigeants ensuite.

Lancez `pytest` dès le clone : tout doit passer. Les tests marqués
"débloqué par TODO n" sautent tant que le TODO n'est pas complété, puis
deviennent de vrais garde-fous. Ajoutez ensuite VOS tests : la politique
de promotion que vous défendrez doit être couverte par des cas à vous.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "feedback"))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def client(monkeypatch):
    """TestClient du service feedback, sur une base SQLite temporaire."""
    tmpdb = Path(tempfile.mkdtemp()) / "fb.db"
    monkeypatch.setenv("FEEDBACK_DB", str(tmpdb))
    import importlib

    from fastapi.testclient import TestClient

    import app.main as m

    importlib.reload(m)
    with TestClient(m.app) as c:
        yield c


def test_health(client):
    """Le service démarre et répond — sinon relisez le README (démarrage)."""
    r = client.get("/health")
    assert r.status_code == 200


def test_unknown_request_id_rejected(client):
    """Un feedback sur un dossier jamais scoré est refusé (404)."""
    r = client.post("/feedback", json={"request_id": "REQ-INEXISTANT", "true_label": 1})
    assert r.status_code == 404


def test_invalid_label_rejected(client):
    """Un label hors {0, 1} est refusé par la validation Pydantic (422)."""
    r = client.post("/feedback", json={"request_id": "REQ-00000", "true_label": 3})
    assert r.status_code == 422


def test_post_valid_feedback_counted(client):
    """Un feedback valide est stocké et compté."""
    r = client.post("/feedback", json={"request_id": "REQ-00000", "true_label": 0})
    assert r.status_code == 201
    assert client.get("/feedback/count").json()["count"] == 1


def test_same_feedback_twice_is_idempotent(client):
    """Débloqué par TODO 3 (main.py) : le rejeu réseau ne crée pas de doublon."""
    payload = {"request_id": "REQ-00001", "true_label": 1}
    client.post("/feedback", json=payload)
    try:
        r = client.post("/feedback", json=payload)
    except sqlite3.IntegrityError:
        pytest.skip("TODO 3 de main.py à compléter (gestion du rejeu)")
    assert r.status_code == 201
    assert client.get("/feedback/count").json()["count"] == 1


def test_contradictory_feedback_returns_409(client):
    """Débloqué par TODO 3 (main.py) : deux vérités opposées → arbitrage humain."""
    client.post("/feedback", json={"request_id": "REQ-00002", "true_label": 0})
    try:
        r = client.post("/feedback", json={"request_id": "REQ-00002", "true_label": 1})
    except sqlite3.IntegrityError:
        pytest.skip("TODO 3 de main.py à compléter (conflit de labels)")
    assert r.status_code == 409


def test_count_exposes_new(client):
    """Débloqué par TODO 2 (main.py) : le trigger lit les feedbacks NON consommés."""
    client.post("/feedback", json={"request_id": "REQ-00003", "true_label": 0})
    body = client.get("/feedback/count").json()
    if "new" not in body:
        pytest.skip("TODO 2 de main.py à compléter (clé `new`)")
    assert body["new"] <= body["count"]


def test_promotion_refused_on_critical_regression():
    """Débloqué par TODO 4 (promotion) : une régression critique bloque la promo.

    Copiez d'abord `scripts/promotion_TEMPLATE.py` → `scripts/promotion.py`.
    """
    try:
        from scripts.promotion import decide_promotion
    except ImportError:
        pytest.skip("scripts/promotion.py à créer depuis promotion_TEMPLATE.py")
    prod = {"f1_macro": 0.61, "recall_default": 0.64}
    cand = {"f1_macro": 0.63, "recall_default": 0.20}
    try:
        decision = decide_promotion(cand, prod)
    except NotImplementedError:
        pytest.skip("TODO 4 de promotion.py à compléter")
    assert decision.promote is False
    assert decision.reason
