"""Politique de promotion (SQUELETTE À COMPLÉTER → scripts/promotion.py).

Ici vit **la décision**, séparée de la mécanique d'entraînement. C'est le geste
attendu en M6-B2 : transformer une politique métier en **fonction testable**.

Pourquoi une fonction pure ? Parce qu'elle se teste sur des **métriques
mockées**, sans entraîner quoi que ce soit :

    prod = {"f1_macro": 0.71, "recall_default": 0.62}
    cand = {"f1_macro": 0.74, "recall_default": 0.65}
    assert decide_promotion(cand, prod).promote is True

Un test de décision qui dépend d'un vrai entraînement casse dès que les données
bougent — et ne teste pas votre règle, mais scikit-learn.

Mini-cours : 04 (réentraînement + promotion).
"""

from __future__ import annotations

from dataclasses import dataclass

# TODO 1 — Plancher de qualité absolu, hérité de M5-B2.
#          Le candidat n'est-il pas simplement cassé ?
THRESHOLDS: dict[str, float] = {
    "f1_macro": 0.60,
    "recall_default": 0.60,
}

# TODO 2 — Quelles métriques sont CRITIQUES, et pourquoi ?
#          À justifier dans decisions.md :
#            - pourquoi le recall de la classe défaut est-il contraignant ?
#              (que coûte un défaut prédit comme remboursé ?)
#            - pourquoi F1 macro plutôt que l'accuracy ?
#              (quel est le taux de défauts dans les données ?)
CRITICAL_METRICS: tuple[str, ...] = ("f1_macro", "recall_default")

# TODO 3 — Tolérance de régression et gain minimum.
#          Sans tolérance, un écart de 3ᵉ décimale (bruit d'échantillonnage)
#          bloque un candidat meilleur sur la métrique métier.
#          Sans gain minimum, un modèle identique est promu pour rien.
TOLERANCE: float = 0.01
MIN_GAIN: float = 0.01


@dataclass(frozen=True)
class PromotionDecision:
    """Résultat d'une décision de promotion.

    Attributes:
        promote: True si le candidat doit remplacer le modèle de production.
        reason: Justification lisible, destinée au journal de décision.
    """

    promote: bool
    reason: str


def decide_promotion(
    candidate: dict[str, float],
    production: dict[str, float],
) -> PromotionDecision:
    """Décide si un modèle candidat doit être promu en production.

    Args:
        candidate: Métriques du candidat sur le jeu de référence.
        production: Métriques du modèle en production, sur le **même** jeu.

    Returns:
        La décision et sa justification.
    """
    # TODO 4 — Dans cet ordre :
    #   1. le plancher de qualité est-il tenu ? sinon → refus motivé
    #   2. une métrique critique recule-t-elle de plus que TOLERANCE ?
    #      → refus motivé, en nommant la métrique et l'écart
    #   3. au moins une métrique progresse-t-elle d'au moins MIN_GAIN ?
    #      sinon → refus (le candidat n'achète rien)
    #   4. sinon → promotion, en explicitant le gain ET l'arbitrage consenti
    #
    # La `reason` finit dans le journal de décision et sera relue par Sophie
    # Léger : elle doit être compréhensible sans le code sous les yeux.
    for metric, min_value in THRESHOLDS.items():
        if candidate.get(metric, -1.0) < min_value:
            return PromotionDecision(
                promote=False,
                reason=(
                    f"plancher de qualité non respecté : {metric}={candidate.get(metric, 0.0):.3f} "
                    f"< {min_value:.3f}"
                ),
            )

    for metric in CRITICAL_METRICS:
        candidate_value = candidate.get(metric, 0.0)
        production_value = production.get(metric, 0.0)
        delta = production_value - candidate_value
        if delta > TOLERANCE:
            return PromotionDecision(
                promote=False,
                reason=(
                    f"régression critique sur {metric} : "
                    f"candidat={candidate_value:.3f}, production={production_value:.3f}, "
                    f"écart={delta:.3f} > tol={TOLERANCE:.3f}"
                ),
            )

    gains = {
        metric: candidate.get(metric, 0.0) - production.get(metric, 0.0)
        for metric in CRITICAL_METRICS
    }
    if gains.get("f1_macro", 0.0) < MIN_GAIN and gains.get("recall_default", 0.0) < MIN_GAIN:
        return PromotionDecision(
            promote=False,
            reason=(
                "le candidat n'apporte pas de gain suffisant : "
                f"gain F1={gains.get('f1_macro', 0.0):.3f}, "
                f"gain recall={gains.get('recall_default', 0.0):.3f}, "
                f"min_gain={MIN_GAIN:.3f}"
            ),
        )

    return PromotionDecision(
        promote=True,
        reason=(
            "gain suffisant et pas de régression critique : "
            f"F1 +{gains.get('f1_macro', 0.0):.3f}, recall +{gains.get('recall_default', 0.0):.3f}"
        ),
    )
