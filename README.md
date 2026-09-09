# M6-B2 — Implémenter la boucle de rétroaction complète (Pyrenex, binôme)

> **Repo template.** Un binôme fait **« Use this template »** →
> `M6-B2-pyrenex-boucle-<binome>` et invite l'autre membre en collaborateur.
> Vous restez avec le binôme de M6-B1 : vous continuez sur votre diagnostic.

## 🚀 Démarrage

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q tests                                   # vert dès le clone ; se durcit avec vos TODO
python scripts/retrain.py --min-feedback 200      # une fois retrain.py complété
```

> Variante `uv` : `uv venv .venv && source .venv/bin/activate` puis
> `uv pip install -r requirements.txt`.
> Dépannage : `No module named pip` → vous êtes dans un venv créé par `uv`,
> utilisez `uv pip install …` (pas `pip install`).

Données fournies : `data/feedbacks_simules.csv` (200 à injecter), `prod_scored.csv`,
`lending_club_train.csv`, `reference_set.csv`. Modèle de base : `models/pyrenex_risk_v2.joblib`.

> ⚠️ **Premier geste : trancher le jeu de référence.** Le `data/reference_set.csv`
> livré ici fait **1500 lignes (17,5 % de défauts)** — ce n'est **pas** celui de
> votre M5-B2 (500 lignes). Or le plancher de votre politique de promotion vient
> de vos **seuils M5-B2**, calibrés sur *votre* jeu. Par défaut : **remplacez ce
> fichier par le vôtre**. Sinon, regelez le golden run et refaites le bootstrap.
> Décision + raison dans `decisions.md` (section « Jeu de référence retenu »).

## 🧭 Ce que vous construisez

Vous construisez **la boucle entière**, à deux. Répartissez-vous les briques,
mais **switchez à mi-parcours** : à la fin, chacun doit avoir écrit la partie
qui compte — la **décision de promotion**. En soutenance de certification, vous
serez seul·e à expliquer cette boucle.

| Brique | À faire | Fichier | Mini-cours |
|---|---|---|---|
| A — Endpoint | `POST /feedback` : valide, stocke, 404 / 409 / idempotent | `services/feedback/` | `01` |
| B — Stockage | SQLite + `used_for_training` + jointure `request_id` | (idem) | `02` |
| C — Réentraînement | `retrain.py` : données → **candidat** → évaluation | `scripts/retrain_TEMPLATE.py` | `04` |
| D — **Promotion** | `decide_promotion()` : la règle qui autorise le déploiement | `scripts/promotion_TEMPLATE.py` | `04`, `05` |
| E — Trigger + CI | cron / `workflow_dispatch`, garde-seuil | `crontab_TEMPLATE.txt`, `.github/workflows/ci.yml` | `03` |

> ⚠️ **Deux questions distinctes.** Le **trigger** répond à *« pourquoi
> réentraîner ? »*. La **promotion** répond à *« pourquoi déployer ? »*. Un
> réentraînement déclenché n'implique aucune mise en production : rejeter un
> candidat est une issue normale, tracée et défendable.

> Contrats d'interface, seuils et politique de promotion : à figer dans
> `decisions_TEMPLATE.md` **avant** de coder.

## ✅ Réussite

- `/feedback` accepte ≥ 200 annotations ; `request_id` inconnu → 404 ;
  feedback contradictoire → 409 ; rejeu à l'identique → sans doublon.
- Réentraînement **sur seuil de feedbacks non consommés** (199 → rien, 200 → trigger).
- Le **candidat** est écrit séparément ; `v2.1.0` n'existe **que** s'il est promu.
- La décision est une **fonction testée sur métriques mockées** (un cas promu,
  un cas rejeté), et chaque exécution est **journalisée**.
- Chaîne CI/CD M5 récupère le tag → Grafana voit v2.1.0.
- **Les deux membres** ont contribué, switch des rôles visible, **journal de bord**.
- Vous savez **défendre votre politique** — mardi, on confronte celles de tous
  les binômes, et vous n'aurez pas tous le même verdict.

## 📚 Ressources

Voir [`./ressources/`](./ressources/) — 5 mini-cours + `liens_officiels.md`.
