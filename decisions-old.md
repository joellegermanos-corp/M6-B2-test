# Décision métier — M6-B2

## Objectif

Cette décision fixe la règle métier de promotion d’un modèle candidat issu d’un réentraînement piloté par les vrais labels reçus en production. Le but n’est pas de “déployer dès que le candidat est meilleur en moyenne”, mais de garantir que le candidat est au moins aussi bon que le modèle actuel sur le même point de décision, avec un gain net identifiablesur les métriques métier critiques.

La logique est explicitement alignée avec la fonction de promotion implémentée dans [scripts/promotion.py](scripts/promotion.py) :

- seuil absolu de qualité à respecter
- tolérance de régression sur les métriques critiques
- gain minimum requis avant promotion
- comparaison stricte du candidat et du modèle de production sur le même jeu de référence

---

## 1. Contrat métier retenu

### Feedback

Le feedback produit par l’API contient :

- `request_id` : identifiant unique de la demande
- `true_label` : 0 ou 1
- `comments` : optionnel, pour contexte humain

Le stockage fait l’objet d’une règle d’intégrité :

- un `request_id` inconnu est rejeté
- un même `request_id` avec le même label est traité comme idempotent
- un même `request_id` avec le label différent est rejeté comme contradiction

Cela évite qu’un mauvais ou un doublon “masque” un vrai signal de correction.

### Trigger de réentraînement

Le déclenchement se fait sur un seuil de feedbacks non consommés, c’est-à-dire les lignes dont `used_for_training = 0`.

On ne compte pas le total des feedbacks, car cela ferait redéclencher continuellement le même candidat tant qu’un feedback ajouté n’a pas été consommé. Le script ne réentraîne que lorsque le nombre de nouveaux feedbacks réellement disponibles pour entraînement atteint le seuil.

Règle de code appliquée :

- `n_new = count(feedbacks[used_for_training == 0])`
- si `n_new < --min-feedback`, on skip
- sinon on construit le dataset d’entraînement candidat

Cela protège le système contre les boucles de réentraînement parasites et rend l’activation explicite.

---

## 2. Jeu de référence retenu

Le point de décision est calculé sur le même jeu de référence pour les deux modèles :

- modèle en production
- modèle candidat

Le jeu retenu est [data/reference_set.csv](data/reference_set.csv).

### Pourquoi ce choix est critique

La politique de promotion ne compare pas des métriques mesurées sur des populations différentes. Si le référentiel change entre la production et le candidat, on compare deux distributions différentes ; le delta de performance devient un artefact de jeu de données, pas une vraie mesure de supériorité du modèle.

Le script impose donc un principe fort :

- la même référence est utilisée pour évaluer le candidat et le modèle de production
- c’est le référentiel d’arbitrage de décision, pas un élément d’entraînement

Cela est indispensable pour que la règle de promotion soit interprétable et reproductible.

---

## 3. Politique de promotion

La politique actuelle est celle codée dans [scripts/promotion.py](scripts/promotion.py) et ne doit pas être écartée par une décision “à l’oreille”.

### 3.1 Plancher de qualité absolue

Les seuils absolus sont :

- `f1_macro >= 0.60`
- `recall_default >= 0.60`

Si l’un de ces seuils est manqué, le candidat est rejeté immédiatement.

### 3.2 Métriques critiques

Les métriques critiques sont :

- `f1_macro`
- `recall_default`

Pourquoi ces deux métriques ?

- `f1_macro` mesure la qualité globale du modèle sur les deux classes, sans se laisser tromper par un taux de défauts très déséquilibré.
- `recall_default` est le point de vigilance métier : il mesure la capacité à détecter les dossiers en défaut, c’est-à-dire le risque à ne pas manquer. Pour une institution de crédit, un défaut classé comme “remboursé” est un faux négatif coûteux en risque financier et en exposition.

C’est donc le bon arbitre entre performance globale et sûreté métier.

### 3.3 Tolérance de régression

La tolérance de régression est :

- `TOLERANCE = 0.01`

Règle : si le candidat est en retard de plus de 1 point de pourcentage sur une métrique critique par rapport à la production, il est rejeté.

Exemple :

- production `recall_default = 0.71`
- candidat `recall_default = 0.69`
- écart = 0.02 > 0.01 → rejet

### 3.4 Gain minimum exigé

Le gain minimum est :

- `MIN_GAIN = 0.01`

Le candidat ne peut être promu que s’il apporte au moins un gain de 1 point de pourcentage sur au moins une métrique critique et qu’il n’introduit pas de régression critique supérieure à la tolérance.

La logique est strictement :

- si manque le plancher → rejet
- si régression critique > tolérance → rejet
- si pas de gain suffisant → rejet
- sinon → promotion

---

## 4. Règle de décision exacte

La règle appliquée est la suivante :

1. Vérifier que le candidat respecte le plancher de qualité.
2. Vérifier qu’aucune métrique critique ne régresse de plus que la tolérance.
3. Vérifier qu’il apporte un gain minimum significatif.
4. Sinon, promouvoir.

Cette logique est intentionnelle : elle évite qu’un modèle “un peu meilleur” soit déployé sans preuve de valeur métier, et évite surtout qu’un modèle légèrement plus mauvais soit promu dans un contexte où le coût de l’erreur est asymétrique.

---

## 5. Décision de rejet ou d’acceptation

### Cas de rejet

Le candidat est rejeté si l’une de ces conditions se produit :

- plancher de qualité non respecté
- baisse critique d’une métrique métier clé au-delà de la tolérance
- gain insuffisant par rapport au modèle actuel

### Cas d’acceptation

Le candidat est accepté si :

- les seuils absolus sont tenus
- aucune métrique critique ne recule au-delà de la tolérance
- le gain net est positif et au moins `0.01`

Le journal de décision doit rendre explicite la raison de la décision, de façon compréhensible sans lire le code.

---

## 6. Règle de doublon et d’intégrité des feedbacks

Le service de feedback applique une politique stricte :

- feedback inconnu → rejet
- même `request_id` + même label → accepté comme idempotent
- même `request_id` + label différent → rejet de contradiction

C’est une règle de gouvernance essentielle : les labels sont des faits métier, pas de simples logs bruités. Un signal contradictoire ne doit pas passer sous silence, car il invalide la base d’apprentissage.

---

## 7. Rationale de l’arbitrage métier

### Pourquoi F1 macro plutôt que l’accuracy ?

Le volume de défauts est rarement équilibré dans un dataset de risque. L’accuracy peut être “bonne” simplement parce que la majorité des dossiers est remboursée, sans rendre le modèle utile pour détecter les défauts.

`f1_macro` donne une vue plus équilibrée sur les deux classes et n’est pas trompé par l’asymétrie du dataset.

### Pourquoi le recall_default est-il si important ?

Parce qu’un défaut classé comme remboursé est précisément le faux négatif coûteux. En pratique, le coût d’un mauvais classement sur la classe défaut est supérieur au coût d’un écart d’optimisation de quelques points de pourcentage sur une autre métrique.

C’est pourquoi cette métrique est contrainte en tant que métrique de sécurité métier.

---

## 8. Point de décision opérationnel

Le flux M6-B2 doit se lire ainsi :

1. les vrais labels arrivent plus tard
2. le feedback est collecté et validé
3. les feedbacks non consommés sont comptés
4. si le seuil est atteint, on déclenche le réentraînement
5. on entraîne un candidat séparément
6. on compare production vs candidat sur le même `reference_set`
7. on applique la règle de décision pure
8. on promote seulement si la décision est positive

Ce point est clé : le déclenchement ne signifie pas le déploiement. Le déploiement est une décision métier séparée de l’entraînement.

---

## 9. Décision de principe finale

Le modèle candidat ne doit pas être promu simplement parce qu’il a été entraîné. Il doit être promu uniquement si :

- il respecte les seuils métier
- il ne recule pas de trop sur les métriques critiques
- il apporte un gain net mesurable sur le même jeu de référence

Cette règle est la base de la gouvernance M6-B2 et la condition minimale pour maintenir la confiance opérationnelle dans le système de réentraînement.
