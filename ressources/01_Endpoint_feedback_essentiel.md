# Endpoint feedback — Mini-cours

> Brief associé : M6-B2
> Durée de lecture : ~20 min
> Pré-requis : FastAPI + Pydantic (M1-B2)

## Pourquoi cette techno ?

Une boucle d'amélioration continue commence par **collecter la vérité terrain** :
un conseiller renvoie la **vraie** classe d'un dossier déjà scoré (a-t-il fait
défaut, oui/non). Cet endpoint `/feedback` est la porte d'entrée de la boucle :
sans annotations, pas de réentraînement utile. On le garde **simple** (un POST
validé), pas une UI d'annotation (autre métier).

## Concepts clés

- **Schéma Pydantic** : `{request_id, true_label (0/1), comments?}`. La
  validation rejette automatiquement un label hors {0,1} (422).
- **Le pont `request_id`** : introduit dans les logs (M1-B2) et le middleware
  (M5-B1), il relie le feedback au dossier scoré (et donc à ses features). Une
  simple **jointure**, pas de réconciliation complexe.
- **Validation métier** : rejeter un `request_id` **inconnu** (404) — on ne
  stocke que des feedbacks rattachables à une prédiction réelle.
- **Idempotence ≠ écrasement** : renvoyer **deux fois le même feedback** ne doit
  rien casser (rejeu réseau). Mais renvoyer **un label différent** sur le même
  `request_id` n'est pas un rejeu, c'est une **contradiction** : deux vérités
  terrain opposées sur le même dossier. Répondez **409** et laissez un humain
  arbitrer. `INSERT OR REPLACE` écraserait la première vérité en silence — et
  cette annotation part ensuite dans le jeu d'entraînement.

  | Cas | Réponse |
  |---|---|
  | `request_id` inconnu | **404** |
  | label hors {0,1} | **422** (Pydantic) |
  | même `request_id`, même label | **201**, sans doublon |
  | même `request_id`, label différent | **409** |
- **Service léger** : une route ajoutée au backend M5, ou un micro-service
  FastAPI dédié — au choix.

## Exemple minimal qui tourne

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

class Feedback(BaseModel):
    request_id: str
    true_label: int = Field(..., ge=0, le=1)
    comments: str | None = None

app = FastAPI()
VALID = {"REQ-00001", "REQ-00042"}  # chargé depuis predictions_log/prod_scored

@app.post("/feedback", status_code=201)
def post_feedback(fb: Feedback):
    if fb.request_id not in VALID:
        raise HTTPException(404, "request_id inconnu")
    # ... stockage ...
    return {"status": "stored"}
```

## Exercice guidé

1. Complétez le service `services/feedback/` : route `POST /feedback` + `/health`
   + `/feedback/count` (qui renvoie le total **et** le nombre de feedbacks non
   consommés — c'est ce dernier qui pilote le trigger).
2. Chargez les `request_id` valides depuis `prod_scored.csv` au démarrage (lifespan).
3. Testez les 4 cas : **insérez successivement** 200 feedbacks valides (un POST
   par feedback, l'endpoint est unitaire) → chaque appel renvoie **201** et
   `GET /feedback/count` renvoie `{"count": 200, "new": 200}` ; un id inconnu →
   **404** ; un label 5 → **422** ; le même `request_id` avec un label opposé →
   **409**.

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| Pas de validation du `request_id` | On stocke des feedbacks orphelins, inutilisables |
| Pas de PK sur `request_id` | Doublons si renvoi |
| Charger les ids valides à chaque requête | Lenteur (charger une fois au lifespan) |
| Label en texte libre | Données sales pour le réentraînement |

| Symptôme | Cause probable |
|---|---|
| 422 inattendu | label hors {0,1} ou champ manquant |
| Feedback non rattachable au réentraînement | `request_id` non validé à l'entrée |
| Doublons en base | pas de `INSERT OR REPLACE` / PK |

## Pour aller plus loin

- FastAPI — Request body : https://fastapi.tiangolo.com/tutorial/body/
- Co-authored commits (pair) : https://docs.github.com/pull-requests/committing-changes-to-your-project/creating-and-editing-commits/creating-a-commit-with-multiple-authors

## Vérification (checklist apprenant)

- [ ] `POST /feedback` valide le schéma (label 0/1).
- [ ] Un `request_id` inconnu est rejeté (404).
- [ ] Les ids valides sont chargés une fois (lifespan).
- [ ] `/feedback/count` renvoie le total stocké.
- [ ] 200 feedbacks s'insèrent sans doublon.
