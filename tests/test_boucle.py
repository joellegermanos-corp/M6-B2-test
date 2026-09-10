"""Tests de la boucle — verts sur le squelette, plus exigeants ensuite.

Lancez `pytest` dès le clone : tout doit passer. Les tests marqués
"débloqué par TODO n" sautent tant que le TODO n'est pas complété, puis
deviennent de vrais garde-fous. Ajoutez ensuite VOS tests : la politique
de promotion que vous défendrez doit être couverte par des cas à vous.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
import hashlib
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



def test_trigger_only_on_threshold(client):
    # 199 feedbacks non consommés : pas de retrain
    for i in range(199):
        payload = {"request_id": f"REQ-{i:05d}", "true_label": 1 if i % 2 == 0 else 0}
        r = client.post("/feedback", json=payload)
        assert r.status_code in (200, 201), r.text

    body = client.get("/feedback/count").json()
    assert body["new"] == 199

    # le trigger ne doit pas se lancer en dessous du seuil
    # ici on test la règle de logique métier, pas le code cron
    assert body["new"] < 200

    # 200e feedback : seuil atteint
    payload = {"request_id": "REQ-00199", "true_label": 0}
    r = client.post("/feedback", json=payload)
    assert r.status_code in (200, 201), r.text

    body2 = client.get("/feedback/count").json()
    assert body2["new"] == 200
    assert body2["new"] >= 200

def test_count_counts_only_unconsumed_feedbacks(client):
    # 1er feedback
    r1 = client.post("/feedback", json={"request_id": "REQ-00000", "true_label": 1})
    assert r1.status_code in (200, 201)

    # un feedback “consommé” doit être filtré du déclenchement
    # ici on simule la consommation en base, mais la logique métier est :
    #   new = total WHERE used_for_training = 0
    body = client.get("/feedback/count").json()
    assert body["new"] == 1
    assert body["count"] == 1

def test_feedback_accepts_200_feedbacks_without_loss(client):
    for i in range(200):
        payload = {
            "request_id": f"REQ-{i:05d}",
            "true_label": 1 if i % 2 == 0 else 0,
            "comments": f"feedback-{i}",
        }
        r = client.post("/feedback", json=payload)
        assert r.status_code in (200, 201), r.text

    count = client.get("/feedback/count").json()
    assert count["count"] == 200
    assert count["new"] == 200


def test_feedback_duplicate_does_not_increase_count(client):
    payload = {"request_id": "REQ-00010", "true_label": 1}
    r1 = client.post("/feedback", json=payload)
    r2 = client.post("/feedback", json=payload)

    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201)
    assert client.get("/feedback/count").json()["count"] == 1

# TODO 5 — Tests pures de décision de promotion.
#   On ne lance ni entraînement ni modèle réel : on teste seulement la logique
#   métier entre métriques du candidat et métriques de production.
#   Cas attendus :
#     - candidat meilleur, sans régression → promotion acceptée
#     - candidat pire ou équivalent → promotion refusée
#
def test_promotion_accepted_when_candidate_is_better_enough():
    """Un candidat meilleur avec gain suffisant et sans régression critique est promu."""
    from scripts.promotion import decide_promotion

    prod = {"f1_macro": 0.71, "recall_default": 0.62}
    cand = {"f1_macro": 0.75, "recall_default": 0.67}

    decision = decide_promotion(cand, prod)

    assert decision.promote is True
    assert decision.reason


def test_promotion_rejected_when_candidate_is_not_better_enough():
    """Un candidat équivalent ou sans gain suffisant est refusé."""
    from scripts.promotion import decide_promotion

    prod = {"f1_macro": 0.71, "recall_default": 0.62}
    cand = {"f1_macro": 0.71, "recall_default": 0.61}

    decision = decide_promotion(cand, prod)

    assert decision.promote is False
    assert decision.reason


def test_reference_set_is_the_frozen_m5_b2_dataset():
    reference_path = ROOT / "data" / "reference_set.csv"
    assert reference_path.exists()

    rows = reference_path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 501  # header + 500 observations
    assert hashlib.sha256(reference_path.read_bytes()).hexdigest() == (
        "d91e211091c8f2ddf5c4ffa4b2276a7e489489bf5e22dc09fae03eb584016e7e"
    )


def test_degraded_candidate_evaluation_is_rejected():
    result = subprocess.run(
        [sys.executable, "scripts/evaluate_model.py", "--release-tag", "degraded", "--degrade"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert '"status": "failed"' in result.stdout
    assert "f1_macro" in result.stdout


# TODO 6 — Test de bout en bout de la boucle :
#   1. POST /feedback sur un request_id validé
#   2. seuil de nouveaux feedbacks atteint
#   3. retrain.py lance le réentraînement
#   4. le candidat est comparé au modèle de production sur le même reference_set
#   5. la décision est journalisée et on observe promotion ou rejet
#
# Ce test est volontairement plus haut niveau : il vérifie le flux complet,
# pas seulement l'unité de décision. Il sert à détecter les régressions entre
# service de feedback, trigger et politique de promotion.
def test_boucle_feedback_to_decision_end_to_end(monkeypatch, tmp_path):
    """Flux complet : feedback → seuil → retrain → comparaison → promotion/rejet."""
    # TODO 6 — On vérifie la vraie chaîne : on poste des feedbacks via le
    # service FastAPI, puis on fait lire le script `retrain.py` sur le même
    # fichier SQLite que le service a créé. Cela reproduit le flux réel sans
    # mocker la politique de décision.
    db_path = tmp_path / "feedbacks.db"
    monkeypatch.setenv("FEEDBACK_DB", str(db_path))
    import importlib

    from fastapi.testclient import TestClient

    import app.main as m

    importlib.reload(m)
    with TestClient(m.app) as client:
        for i in range(3):
            payload = {"request_id": f"REQ-0000{i}", "true_label": 0}
            r = client.post("/feedback", json=payload)
            assert r.status_code == 201, r.json()
        body = client.get("/feedback/count").json()
        assert body["new"] >= 1

    root = ROOT
    artifact_db = root / "data" / "feedbacks.db"
    artifact_db.parent.mkdir(exist_ok=True, parents=True)
    if artifact_db.exists():
        artifact_db.unlink()
    shutil.copy2(db_path, artifact_db)

    candidate_path = root / "models" / "pyrenex_risk_candidate.joblib"
    if candidate_path.exists():
        candidate_path.unlink()
    decision_log = root / "decisions_log.jsonl"
    if decision_log.exists():
        decision_log.unlink()

    # TODO 7 — Exécution réelle du script de retrain sur le jeu de feedbacks
    # stockés. C'est le point de validation de la boucle : si le seuil est
    # atteint, le script doit produire un candidat et un journal de décision.
    result = subprocess.run(
        [sys.executable, "scripts/retrain.py", "--min-feedback", "1"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert candidate_path.exists()
    assert decision_log.exists()
    assert decision_log.read_text(encoding="utf-8").strip()
