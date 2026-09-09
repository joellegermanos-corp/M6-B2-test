# Trigger de réentraînement (cron) — Mini-cours

> Brief associé : M6-B2
> Durée de lecture : ~20 min
> Pré-requis : ligne de commande, notion de job planifié

## Pourquoi cette techno ?

Réentraîner **à chaque feedback** serait absurde (coûteux, instable). On déclenche
**périodiquement et sous condition** : « toutes les 6 h, **si** au moins 200
nouveaux feedbacks, réentraîne ». Le **cron** (planificateur OS) suffit pour ça —
pas besoin d'un orchestrateur lourd (Prefect/Airflow) pour M6.

## Concepts clés

- **cron** : une ligne `* * * * * commande` planifie une exécution. `0 */6 * * *`
  = toutes les 6 h. (Testez votre expression sur crontab.guru.)
- **Garde-seuil** : le script vérifie **avant** d'agir que le nombre de
  feedbacks **non encore consommés** atteint le seuil ; sinon il **ne fait rien**
  et sort en succès (exit 0). Ce n'est pas une erreur.
- ⚠️ **Compter les nouveaux, pas le total.** `COUNT(*) >= 200` est un piège : une
  fois les 200 atteints, la condition reste vraie **pour toujours** et le cron
  réentraîne toutes les 6 h sur les mêmes données. On compte
  `WHERE used_for_training = 0`, et on marque les lignes consommées après un
  entraînement réussi.
- 🎯 **Le trigger ne décide pas du déploiement.** Il répond à *« pourquoi
  réentraîner ? »*. La question *« pourquoi déployer ? »* est une **décision
  séparée** (cf. mini-cours 04). Un réentraînement déclenché peut parfaitement
  se terminer par un rejet : c'est une issue normale.
- **Idempotence** : relancer le job ne doit pas casser l'état (pas de double
  réentraînement concurrent ; lock simple si besoin).
- **Déclenchement manuel** : en CI, `workflow_dispatch` permet de lancer le
  réentraînement à la demande (utile pour la démo).
- **Anti-spam** : marquer les feedbacks consommés **après un entraînement
  réussi** est ce qui rend le trigger sain — c'est le même mécanisme que le
  comptage ci-dessus, vu de l'autre bout.
- ⭐ **Second déclencheur (bonus, facultatif)** : « ou dérive confirmée », branché
  sur la détection M6-B1. À ne tenter **qu'une fois la boucle complète verte** :
  deux mécanismes à déboguer en 6 h font dérailler le planning, et « dérive
  confirmée » doit renvoyer à une **fonction concrète** de M6-B1, sinon le critère
  n'est pas vérifiable.

## Exemple minimal qui tourne

```bash
# crontab.txt — toutes les 6h
0 */6 * * * cd /opt/pyrenex && .venv/bin/python scripts/retrain.py --min-feedback 200 >> logs/retrain.log 2>&1
```

```python
# garde-seuil dans retrain.py — on compte les NON CONSOMMÉS
n_new = int((feedbacks["used_for_training"] == 0).sum())
if n_new < args.min_feedback:
    print({"action": "skip", "reason": f"{n_new} nouveaux < {args.min_feedback}"})
    return 0                              # rien à faire, pas une erreur
```

## Exercice guidé

1. Écrivez l'expression cron pour « toutes les 6 h » et vérifiez-la sur
   crontab.guru.
2. Implémentez le garde-seuil dans `retrain.py` : 199 **nouveaux** feedbacks →
   skip (exit 0), 200 → exécute.
   Puis vérifiez le piège : relancez **immédiatement** après un entraînement
   réussi. Si le job se redéclenche, c'est que vous comptez le total.
3. Ajoutez `workflow_dispatch` au workflow CI pour le déclenchement manuel.

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| Réentraîner à chaque feedback | Coût + instabilité |
| Garde-seuil qui renvoie une erreur quand < seuil | Le cron « échoue » à tort |
| Chemins relatifs dans le cron | Job qui ne trouve pas les fichiers (cron part de `$HOME`) |
| Pas de log redirigé | Échec silencieux, indébogable |

| Symptôme | Cause probable |
|---|---|
| Le cron « échoue » tout le temps | chemins relatifs / venv non activé |
| Réentraînements en boucle | feedbacks non consommés/marqués |
| Rien ne se passe | expression cron fausse (tester sur crontab.guru) |

## Pour aller plus loin

- crontab.guru : https://crontab.guru/
- GitHub Actions — workflow_dispatch : https://docs.github.com/actions/using-workflows/manually-running-a-workflow

## Vérification (checklist apprenant)

- [ ] Mon expression cron est validée (crontab.guru).
- [ ] Le garde-seuil sort en **succès** (exit 0) sous le seuil.
- [ ] Le job utilise des chemins absolus + venv.
- [ ] `workflow_dispatch` permet le déclenchement manuel.
- [ ] Les logs sont redirigés (pas d'échec silencieux).

> 💡 **Récap** : on réentraîne **périodiquement et sous condition** (toutes les 6 h,
> **si** ≥ seuil de feedbacks). Le garde-seuil sort en **succès** (exit 0) sous le seuil —
> ce n'est pas une erreur. Chemins **absolus** + venv dans le cron, logs redirigés,
> `workflow_dispatch` pour la démo manuelle. Tester l'expression sur crontab.guru.

*Anti-spam : après un réentraînement, marquer/consommer les feedbacks pour ne pas re-déclencher aussitôt.*
