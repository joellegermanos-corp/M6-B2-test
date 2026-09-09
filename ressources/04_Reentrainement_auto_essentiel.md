# Réentraînement automatique + garde-fous — Mini-cours

> Brief associé : M6-B2
> Durée de lecture : ~25 min
> Pré-requis : Pipeline scikit-learn (M1), évaluation continue (M5-B2)

## Pourquoi cette techno ?

Le cœur de la boucle : produire un **nouveau modèle** à partir des données
récentes + feedbacks, **automatiquement** — mais **jamais à l'aveugle**. Un
réentraînement non contrôlé peut produire un modèle **pire** et le déployer. Les
garde-fous (contract test + évaluation continue **avant** le tag) garantissent
qu'on ne met en prod qu'une version au moins aussi bonne.

## Concepts clés

- **Réutiliser, pas réinventer** : on reprend la **Pipeline M1** (`preprocess.py`
  + mêmes hyperparams). On change la **donnée** (train + feedbacks), pas la recette.
- **Enrichir le train** : joindre les feedbacks (`request_id → true_label`) à
  leurs features (via `prod_scored`) et les ajouter au train initial.
- ⚠️ **Le `reference_set` n'entre JAMAIS dans l'entraînement.** C'est un jeu de
  contrôle **fixe** : dès qu'il sert à entraîner, il cesse de mesurer quoi que
  ce soit et toutes les comparaisons deviennent flatteuses.

  | Jeu | Rôle | Entre dans le train ? |
  |---|---|---|
  | `lending_club_train` | historique | ✅ |
  | feedbacks validés | vérités terrain récentes | ✅ |
  | `reference_set` | arbitre de comparaison | ❌ **jamais** |

- **Candidat ≠ modèle promu** : l'entraînement produit
  `pyrenex_risk_candidate.joblib`. Il ne devient `v2.1.0` **qu'après** décision
  favorable. Nommer `v2.1.0` un modèle qu'on va peut-être rejeter crée une
  version fantôme qui n'a jamais existé en production.
- **Contract test** : le modèle accepte le schéma attendu et sort une proba ∈
  [0,1]. Garde-fou de **non-régression de schéma**.
- **Deux garde-fous, pas un** :
  1. **plancher de qualité** absolu (seuils M5-B2) — le candidat n'est pas cassé ;
  2. **non-régression face à la production** — le candidat mérite la place.
  Un candidat peut passer le plancher **et** être rejeté parce qu'il n'apporte
  rien de mieux que le modèle déjà en service.
- **Comparer à armes égales** : candidat et production sont évalués sur le
  **même** `reference_set`, avec le **même** code. Sinon on compare deux mesures,
  pas deux modèles.
- **Le rejet n'est pas une panne** : `retrain.py` sort **0** dans les deux cas
  (promu ou rejeté) et **journalise la décision**. Un `exit 1` est réservé aux
  vraies erreurs (contract test KO). Une CI rouge à chaque rejet ferait
  désactiver l'alerte au bout de trois jours.
- **Redéploiement** : **si et seulement si** promotion, tag `v2.1.0` → la CI/CD
  M5 build/push l'image.

## Exemple minimal qui tourne

```python
# 1. Un CANDIDAT, pas encore une version officielle
candidate = Pipeline([("prep", build_preprocessor()),
                      ("clf", RandomForestClassifier(n_estimators=200, max_depth=10,
                       min_samples_leaf=10, class_weight="balanced", random_state=42))])
candidate.fit(X_train_plus_feedback, y_train_plus_feedback)
joblib.dump(candidate, "models/pyrenex_risk_candidate.joblib", compress=3)

# 2. Les DEUX modèles mesurés sur le MÊME jeu de référence
cand_metrics = evaluate(candidate)
prod_metrics = evaluate(joblib.load("models/pyrenex_risk_v2.joblib"))

# 3. La décision est isolée dans une fonction testable
decision = decide_promotion(cand_metrics, prod_metrics)
log_decision(decision, cand_metrics, prod_metrics)   # traçabilité, toujours

if decision.promote:
    joblib.dump(candidate, "models/pyrenex_risk_v2_1.joblib", compress=3)
    # puis : git tag v2.1.0 → CI/CD M5
```

## Exercice guidé

1. Complétez `retrain.py` : `build_training_data`, `train_candidate`,
   `evaluate_candidate` — en gardant le `reference_set` hors du train.
2. Écrivez `decide_promotion()` dans `scripts/promotion.py` et **testez-la sur
   des métriques mockées** : un dict candidat, un dict production, aucune
   dépendance à scikit-learn.

   ```python
   prod = {"f1_macro": 0.71, "recall_default": 0.62}
   cand = {"f1_macro": 0.74, "recall_default": 0.65}
   assert decide_promotion(cand, prod).promote is True

   cand_pire = {"f1_macro": 0.68, "recall_default": 0.65}
   assert decide_promotion(cand_pire, prod).promote is False
   ```

3. Prouvez le garde-fou **en conditions réelles** : dégradez volontairement le
   candidat (moins de données, labels mélangés) → la décision doit être un
   **rejet journalisé**, et **aucun tag** ne doit être produit.

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| Promouvoir sans comparer à la production | Un modèle équivalent ou pire remplace un modèle qui marchait |
| Mettre le `reference_set` dans le train | L'arbitre devient juge et partie, toute comparaison est faussée |
| Nommer `v2.1.0` un candidat non validé | Version fantôme jamais partie en prod, historique illisible |
| Évaluer candidat et prod sur des jeux différents | On compare deux mesures, pas deux modèles |
| Tester la promotion via un vrai entraînement | Test instable, qui casse quand les données bougent |
| Recoder une nouvelle Pipeline | Incohérence avec le modèle servi |
| Sortir en erreur (`exit 1`) sur un rejet | Le rejet est normal ; une CI rouge en permanence finit ignorée |
| Oublier la jointure feedback↔features | Feedbacks inutilisables pour l'entraînement |
| Non-déterminisme | Résultats non reproductibles (fixer `random_state`) |

| Symptôme | Cause probable |
|---|---|
| Le candidat est toujours promu | aucune comparaison à la production, ou règle en `>=` sans exigence de gain |
| Le candidat est toujours rejeté | le jeu d'entraînement fourni est plus pauvre que celui du modèle de prod — vérifier qu'on réentraîne bien sur la même base |
| Métriques du candidat trop belles | le `reference_set` a fui dans le train |
| `KeyError` features | jointure `request_id` ratée |
| Le test de promotion casse au moindre changement de données | il dépend d'un entraînement réel au lieu de métriques mockées |

## Pour aller plus loin

- scikit-learn Pipeline : https://scikit-learn.org/stable/modules/generated/sklearn.pipeline.Pipeline.html
- MLOps principles : https://ml-ops.org/content/mlops-principles

## Vérification (checklist apprenant)

- [ ] Je réutilise la Pipeline M1 (pas une nouvelle).
- [ ] J'enrichis le train avec les feedbacks (jointure features).
- [ ] Le `reference_set` ne sert **jamais** à entraîner.
- [ ] J'écris un **candidat**, renommé `v2.1.0` seulement après promotion.
- [ ] J'évalue candidat **et** production sur le **même** jeu de référence.
- [ ] Ma décision de promotion est une **fonction testée sur métriques mockées**.
- [ ] Chaque exécution est **journalisée** (promue ou rejetée).
- [ ] Un rejet ne produit **aucun tag** — vérifié au moins une fois.
- [ ] Résultats reproductibles (`random_state` fixé).

> 💡 **Récap** : on **réutilise** la Pipeline M1 (on change la donnée, pas la
> recette), on garde le `reference_set` **hors du train**, on produit un
> **candidat** qui doit **gagner sa promotion** face au modèle en place — et on
> **trace la décision** dans les deux cas. Entraîner un modèle et décider de le
> mettre en production sont **deux opérations différentes**.
