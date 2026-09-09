# Stockage des feedbacks — Mini-cours

> Brief associé : M6-B2
> Durée de lecture : ~20 min
> Pré-requis : SQLite (M3), notion de jointure

## Pourquoi cette techno ?

Les feedbacks collectés doivent être **stockés proprement** pour servir au
réentraînement : sans intégrité (doublons, écrasements) ni traçabilité, la
boucle réentraîne sur de la donnée sale. Ici le stockage est **imposé :
SQLite**, hérité de M3 — vous connaissez déjà le module `sqlite3`, le schéma
et la jointure. L'alternative **CSV versionné** est présentée plus bas pour que
vous sachiez *pourquoi* elle est écartée : c'est l'arbitrage qu'il faut savoir
défendre, pas le choix qu'il faut refaire. Ce que vous tranchez dans
`decisions.md`, c'est le **schéma**, la **politique de doublon** et la gestion
de `used_for_training`.

## Concepts clés

- **SQLite** (imposé, hérité de M3) : base fichier, PK sur `request_id`
  (anti-doublon), jointures SQL vers `prod_scored`. Robuste à la concurrence
  d'écriture — utile dès qu'on est deux à pousser des feedbacks.
- **CSV versionné** (alternative écartée) : simple, lisible dans Git, mais
  **pas de garantie d'unicité** ni de gestion de la concurrence — et un
  conflit de merge à chaque ligne ajoutée par le binôme.
- **Schéma minimal** : `request_id (PK)`, `true_label`, `comments`, `created_at`,
  **`used_for_training` (défaut 0)**.
- ⚠️ **`used_for_training` n'est pas un luxe** : sans lui, le trigger compte le
  **total** et redéclenche un réentraînement à chaque passage du cron une fois le
  seuil franchi. On marque les lignes consommées après un entraînement réussi.
- **Un feedback reçu n'est pas un feedback fiable.** Il devient une donnée
  d'entraînement : une annotation fausse ou mal rattachée dégrade le prochain
  modèle. Validez systématiquement — `request_id` existant, label ∈ {0,1}, pas de
  doublon silencieux, horodatage présent.
- **Politique de doublon, à trancher explicitement** : même `request_id` + **même**
  label → idempotent (un rejeu réseau ne doit rien casser). Même `request_id` +
  label **différent** → **409 Conflict**. Deux vérités terrain contradictoires sur
  le même dossier relèvent d'un arbitrage humain, pas d'un écrasement silencieux.
- **Jointure** : `feedbacks ⋈ prod_scored ON request_id` récupère les
  **features** du dossier → base d'entraînement enrichie.
- **RGPD** : ne stocker que le nécessaire (`request_id` + label). Pas de PII dans
  la table de feedback ; la jointure vers les features reste interne.
- **Rétention** : décider combien de temps on garde les feedbacks (et pourquoi).

## Exemple minimal qui tourne

```python
import sqlite3
con = sqlite3.connect("feedbacks.db")
con.execute("""CREATE TABLE IF NOT EXISTS feedbacks (
    request_id TEXT PRIMARY KEY, true_label INTEGER NOT NULL,
    comments TEXT, created_at TEXT NOT NULL,
    used_for_training INTEGER NOT NULL DEFAULT 0)""")

# On lit AVANT d'écrire : un conflit doit être détecté, pas écrasé.
row = con.execute("SELECT true_label FROM feedbacks WHERE request_id = ?",
                  ("REQ-00042",)).fetchone()
if row is None:
    con.execute("INSERT INTO feedbacks (request_id, true_label, comments, created_at)"
                " VALUES (?,?,?,?)",
                ("REQ-00042", 1, "annotation", "2026-06-10T10:00:00Z"))
elif row[0] != 1:
    raise ValueError("feedback contradictoire → 409, arbitrage métier requis")
con.commit()

total = con.execute("SELECT COUNT(*) FROM feedbacks").fetchone()[0]
new = con.execute("SELECT COUNT(*) FROM feedbacks WHERE used_for_training = 0").fetchone()[0]
print(f"total={total} | non consommés={new}")   # c'est `new` qui pilote le trigger
```

## Exercice guidé

1. En groupe : SQLite **ou** CSV ? Tranchez et écrivez la raison dans `decisions.md`.
2. Implémentez le stockage + un script de **jointure** feedbacks ⋈ prod_scored.
3. Vérifiez les trois cas : rejeu à l'identique → idempotent ; label
   contradictoire → **409** ; `request_id` inconnu → **404**.
4. Vérifiez que `COUNT(*)` et le compte des non-consommés **divergent** après
   avoir marqué des lignes `used_for_training = 1`.

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| CSV sans verrou à deux mains | écritures concurrentes corrompues, conflits de merge à chaque feedback |
| Pas de PK | doublons → réentraînement biaisé |
| `INSERT OR REPLACE` pour « gérer » les doublons | écrase silencieusement une vérité terrain ; en SQLite c'est un DELETE+INSERT, avec effets de bord sur les contraintes |
| Compter le total pour le trigger | réentraînements en boucle sur les mêmes données |
| Stocker des PII dans la table feedback | risque RGPD |
| Pas d'horodatage | impossible de gérer la rétention / l'ordre |

| Symptôme | Cause probable |
|---|---|
| Doublons en base | pas de PK |
| Une vérité terrain a disparu sans trace | `INSERT OR REPLACE` : il écrase (voire supprime puis réinsère la ligne) |
| Le cron réentraîne en boucle | le trigger compte le total au lieu des non-consommés |
| Jointure vide | `request_id` non aligné entre feedback et prod |
| Conflits Git sur le CSV | stockage fichier plat inadapté dès qu'on écrit à deux |

## Pour aller plus loin

- Python sqlite3 : https://docs.python.org/3/library/sqlite3.html
- CNIL — durées de conservation : https://www.cnil.fr/fr/la-gestion-des-ressources-humaines

## Vérification (checklist apprenant)

- [ ] Le schéma, la politique de doublon et `used_for_training` sont tranchés et justifiés dans `decisions.md`.
- [ ] Je sais expliquer pourquoi SQLite plutôt qu'un CSV versionné.
- [ ] Schéma avec PK `request_id` + horodatage.
- [ ] Jointure feedbacks ⋈ prod_scored fonctionnelle.
- [ ] Pas de doublon à la ré-insertion.
- [ ] Pas de PII stockée.

> 💡 **Récap** : **SQLite** est imposé (héritage M3) et l'emporte sur le CSV
> versionné dès qu'on écrit à plusieurs (intégrité, PK anti-doublon, pas de
> conflit de concurrence). Schéma minimal `request_id (PK)` /
> `true_label` / `comments` / `created_at`. La **jointure** vers `prod_scored` récupère
> les features pour le réentraînement. RGPD : pas de PII dans la table de feedback.
