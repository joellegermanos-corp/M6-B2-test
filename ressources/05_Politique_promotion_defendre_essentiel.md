# Formaliser et défendre une politique de promotion — Mini-cours

> Brief associé : M6-B2
> Durée de lecture : ~20 min
> Pré-requis : réentraînement + garde-fous (mini-cours `04`), métriques M4/M6-B1

## Pourquoi cette techno ?

Un modèle réentraîné n'a **aucun droit acquis** à remplacer celui qui tourne. La
question « faut-il le déployer ? » n'est pas technique, elle est **métier** : que
coûte une erreur, quel gain justifie le risque d'un redéploiement, qu'est-ce
qu'on accepte de perdre en échange de quoi.

Le geste professionnel attendu ici, c'est de transformer cette question en une
**règle écrite, testable et défendable**. Tant qu'elle reste dans la tête de
celui qui a codé le script, ce n'est pas une politique — c'est une habitude.

C'est le cœur de C9 niveau *transposer* : pas « savoir réentraîner », mais
**savoir décider**, et savoir l'expliquer à Sophie Léger.

## Concepts clés

- **Une politique, pas un seuil isolé.** Une règle utilisable combine trois
  choses : un **plancher** (le candidat n'est pas cassé), une **non-régression**
  (il ne dégrade rien d'important), un **gain minimum** (il apporte assez pour
  justifier le déploiement).
- **Métriques critiques = choix métier.** Dire « recall de la classe défaut est
  critique » revient à dire : *un dossier risqué accepté à tort coûte plus cher
  qu'un bon dossier refusé à tort*. Si vous ne pouvez pas formuler la phrase en
  euros ou en risque, votre métrique n'est pas justifiée.
- **La tolérance rend la règle utilisable.** Sans elle, un écart de 3ᵉ décimale
  — du bruit d'échantillonnage — bloque un candidat meilleur là où ça compte.
  Avec une tolérance trop large, n'importe quoi passe. Sa valeur est un
  **arbitrage à assumer**, pas une constante universelle.
- **Le gain minimum évite les redéploiements gratuits.** Redéployer a un coût et
  un risque. Un candidat rigoureusement équivalent n'achète rien.
- **Une fonction pure se teste, une politique implicite ne se teste pas.**

  ```python
  decide_promotion(candidate: dict, production: dict) -> PromotionDecision
  ```

  Aucune dépendance à scikit-learn : deux dictionnaires en entrée, une décision
  motivée en sortie. C'est ce qui la rend vérifiable **et** discutable.
- **La `reason` fait partie du livrable.** Elle finit dans le journal de
  décision, et sera relue des mois plus tard par quelqu'un qui n'a pas le code
  sous les yeux. *« REJECT »* ne suffit pas ; *« recall_default 0.64 → 0.55,
  au-delà de la tolérance de 0.01 »* se comprend seul.

## Exemple minimal qui tourne

```python
prod = {"f1_macro": 0.6138, "recall_default": 0.6426}
cand = {"f1_macro": 0.6070, "recall_default": 0.6540}

d = decide_promotion(cand, prod)
print(d.promote, "—", d.reason)
# True — Gain net : recall_default +0.0114.
#        Arbitrage assumé : f1_macro recule de -0.0068, dans la tolérance de 0.01
```

Lisez bien ce cas : le candidat est **moins bon** en F1 macro. Et il est promu
quand même, parce qu'il détecte **plus de défauts** — ce qui est l'enjeu métier.
Voilà une décision qui se défend. « Toutes les métriques montent » aurait été
confortable, mais n'aurait rien appris.

## Exercice guidé

1. Écrivez votre règle **en français** dans `decisions.md`, avant de coder :
   *« On promeut si… sauf si… parce que… »*
2. Traduisez-la en `decide_promotion()`, puis testez-la sur 4 cas construits à
   la main : gain net, régression critique, candidat identique, sous le plancher.
3. Lancez la boucle sur vos vraies données. **Le verdict vous surprend ?** C'est
   le moment intéressant : votre règle est-elle mauvaise, ou est-ce votre
   intuition qui l'était ?
4. Préparez votre **fiche de position** (1 page) : vos seuils, vos chiffres,
   votre verdict, et la phrase que vous direz à un binôme qui a tranché
   autrement.

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| Règle en `>=` seulement | Un modèle identique est promu pour rien |
| Aucune tolérance | Un candidat meilleur est rejeté sur du bruit |
| Tolérance choisie après avoir vu le résultat | Ce n'est plus une politique, c'est une justification a posteriori |
| Métriques critiques non justifiées en langage métier | Recette appliquée, pas décision assumée |
| `reason` vide ou cryptique | Journal inexploitable, décision non auditable |
| Décision noyée dans `retrain.py` | Intestable, donc jamais testée |

| Symptôme | Cause probable |
|---|---|
| Le candidat est toujours promu | pas de comparaison à la production, ou pas d'exigence de gain |
| Le candidat est toujours rejeté | métrique critique trop stricte, ou base d'entraînement plus pauvre que celle du modèle en place |
| Impossible d'expliquer le verdict au RDV | la règle n'a jamais été écrite en français avant d'être codée |
| Deux binômes, mêmes données, verdicts opposés | **normal** — les politiques diffèrent. La question est : laquelle se défend le mieux ? |

## Pour aller plus loin

- Google — *Rules of Machine Learning* (règles 14 à 20, mise en production) :
  https://developers.google.com/machine-learning/guides/rules-of-ml
- MLOps principles — *model governance* : https://ml-ops.org/content/mlops-principles
- Martin Fowler — *Continuous Delivery for ML* (section « promotion ») :
  https://martinfowler.com/articles/cd4ml.html

## Vérification (checklist apprenant)

- [ ] Ma règle est écrite **en français** dans `decisions.md`, avec sa raison métier.
- [ ] Elle est implémentée dans une **fonction pure**, hors de `retrain.py`.
- [ ] Elle est testée sur des **métriques mockées**, pas un entraînement réel.
- [ ] Je sais dire pourquoi `recall_default` est contraignant **en langage métier**.
- [ ] Je sais dire pourquoi F1 macro plutôt que l'accuracy.
- [ ] Ma `reason` est compréhensible sans le code sous les yeux.
- [ ] Je peux défendre mon verdict face à un binôme qui a tranché autrement.

> 💡 **Récap** : entraîner un modèle et décider de le déployer sont **deux
> opérations différentes**. La seconde est une décision métier, qui s'écrit, se
> teste et se défend. Un binôme qui a rejeté son candidat **en sachant dire
> pourquoi** a mieux réussi ce brief qu'un binôme qui a promu le sien sans savoir
> ce que sa règle garantissait.
