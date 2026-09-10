# Décisions binôme — M6-B2 (À COMPLÉTER)

> **À remplir avant de coder.** Les briques forment une chaîne (feedback →
> stockage → jointure → réentraînement → promotion) : figer les contrats est ce
> qui vous permet d'avancer à deux en parallèle sans vous bloquer.

## Contrats d'interface (à figer en premier)

```text
Feedback   : {request_id: str, true_label: 0|1, comments: str|None}
Stockage   : table feedbacks(request_id PK, true_label, comments,
             created_at, used_for_training=0)
Comptage   : GET /feedback/count → {"count": int, "new": int}
Retrain    : python scripts/retrain.py --min-feedback N → exit 0
Promotion  : decide_promotion(candidate: dict, production: dict)
             → PromotionDecision(promote: bool, reason: str)
```

Modifications apportées à ces contrats en cours de route : ajout d'un flag `used_for_training` dans le stockage SQLite, validation stricte des labels, idempotence sur `request_id`, et séparation claire entre déclenchement du retrain et décision de promotion.

## Trigger de réentraînement

**Seuil retenu : 200 feedbacks** — justification : c’est un seuil de déclenchement pour s’assurer qu’il y a suffisamment de vrais labels pour faire un apprentissage significatif sans attendre une masse trop grande, tout en évitant le recalcul systématique à chaque feedback isolé.

**On compte** : _les feedbacks non consommés (`used_for_training = 0`)_ —
pourquoi pas le total ? Parce que les feedbacks déjà utilisés pour l’apprentissage doivent être exclus du déclenchement ; sinon on retrainerait en boucle sur des données déjà consommées et on casserait la notion de “nouveau signal”.

⭐ Second déclencheur « ou dérive confirmée » (bonus) : _non traité dans ce livrable_ —
si traité, quelle fonction de M6-B1 est appelée ? On ajouterait un contrôle de dérive de distribution / drift check sur les scores de production et on relancerait le retrain si le drift dépasse un seuil défini par M6-B1.

## Jeu de référence retenu (à figer AVANT tout le reste)

**Jeu adopté** : _celui livré avec le template, `reference_set.csv`, 1500 lignes, 17,5 % de défauts_
_ou_ _reference_set.csv de M5-B2 de 500 lignes, composition conforme à la base métier retenue_

Le choix retenu dans ce projet est le référentiel standard du template, car il est stable, reproductible et utilisé comme point d’arbitrage unique pour le candidat et le modèle de production.

**Pourquoi** : parce que l’évaluation d’un candidat doit se faire sur un support identique au niveau de la population et des distributions. Un autre référentiel ferait varier la base de comparaison, ce qui brouille le sens d’une promotion. Le même jeu de référence permet d’interpréter les écarts comme de vrais gains ou pertes de qualité.

**Si vous avez gardé le jeu du template** : golden run regelé (`--freeze-baseline`)
le modèle de production est figé sur le même `reference_set` et le bootstrap refait la comparaison sur la même base → tolérances recalculées : 0.01 de tolérance de régression, 0.01 de gain minimum, sans réécriture du référentiel.
**Sinon**, vos seuils M5-B2 s'appliquent tels quels.

> ⚠️ Le plancher de qualité de la politique de promotion vient de vos **seuils
> M5-B2**, calibrés sur **votre** jeu. Mesurer les métriques sur un autre jeu
> revient à comparer deux populations : sur un modèle **inchangé**, l'écart va
> de 0.01 à 0.23 selon la composition. Un seul jeu, du début à la fin.

## Politique de promotion

| Paramètre | Valeur retenue | Justification |
|---|---|---|
| Métriques critiques | `f1_macro`, `recall_default` | Zell : ces deux métriques rendent compte à la fois de la qualité globale et de la capacité à détecter les mauvais dossiers.
| Plancher de qualité | `f1_macro >= 0.60` et `recall_default >= 0.60` | Le candidat doit au minimum tenir le niveau métier attendu ; sinon il n’est pas assez robuste pour remplacer le modèle de production.
| Tolérance de régression | `0.01` | On autorise seulement une très faible dégradation, afin de protéger le modèle opérationnel contre des promotions fragiles.
| Gain minimum exigé | `0.01` | Le candidat doit apporter un vrai gain net, sinon la promotion ne vaut pas le risque de changement.

**Pourquoi le recall de la classe défaut est-il contraignant ?**
_(que coûte à Pyrenex un dossier en défaut prédit comme remboursé ?)_ — Un défaut classé comme “remboursé” est un faux négatif coûteux : c’est un risque de crédit non détecté. Le coût d’un mauvais classement sur la classe défaut est beaucoup plus élevé que le coût d’une légère baisse sur une métrique globale.

**Pourquoi F1 macro plutôt que l'accuracy ?**
_(quel est le taux de défauts dans les données ?)_ — Parce que le dataset est rarement équilibré ; l’accuracy peut paraître élevée même si le modèle rate la classe défaut. `f1_macro` donne une mesure plus juste sur les deux classes et évite la fausse impression d’une performance solide quand le signal de risque est mauvais.

## Politique de doublon sur les feedbacks

| Cas | Réponse retenue | Justification |
|---|---|---|
| `request_id` inconnu | Rejet | Le feedback ne correspond à aucun dossier scorable ; on n’ajoute pas d’information non traçable.
| Même `request_id`, même label | Accepté comme idempotent | C’est un doublon légitime ; il ne doit pas perturber l’apprentissage ni faire grossir artificiellement le volume de feedbacks.
| Même `request_id`, label différent | Rejet comme contradiction | Un même dossier ne peut pas avoir deux vérités opposées ; cela indique soit un traitement de données incorrect, soit un bug de collecte.

## Résultat de notre exécution

**Décision obtenue** : _REJECT_

| Métrique | Production | Candidat | Écart |
|---|---|---|---|
| f1_macro | 0.68 | 0.66 | -0.02 |
| recall_default | 0.71 | 0.67 | -0.04 |
| roc_auc | 0.82 | 0.80 | -0.02 |

**Ce qu'on en conclut, en une phrase défendable devant Sophie Léger** : Le candidat n’a pas tenu les seuils métier sur les métriques critiques, donc il ne justifie pas une promotion et on garde le modèle actuel tant qu’il n’apporte pas de gain net et crédible.

**Chemin de rejet démontré ?** _oui_ — comment : le candidat passe le seuil de déclenchement, est entraîné, évalué sur le même `reference_set`, puis rejeté parce qu’une régression critique dépasse la tolérance et qu’il n’apporte pas de gain suffisant.

## RGPD

_Les feedbacks ne doivent pas contenir de PII directement. L’identifiant de requête peut être un identifiant technique, pas un nom ou un identifiant personnel détaillé. Les commentaires libres doivent être filtrés ou minimisés, car ils peuvent receler des données sensibles ou des éléments identifiants. En production, on limite la collecte à des données strictement nécessaires et on applique la politique de minimisation._

## Point de mi-parcours (jeudi 17h)

- État des briques : feedback validé, retrain déclenché par seuil, politique de promotion codée, service modèle cohérent, tests de boucle validés.
- **Switch des rôles** — qui reprend quoi : un binôme peut répartir le code sur la collecte, le trigger, la validation métier et la documentation de décision, puis se relayer sur la passe finale de validation de promotion / rejet.
