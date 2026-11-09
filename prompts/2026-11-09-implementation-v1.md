# Prompt du 2026-11-09 — implémentation V1

## Demande

> @Selascode-agent Implémente la V1 du projet QCM.
>
> Objectif de ce ticket : séance complète de 5 étapes avec redémarrage
> serveur au milieu, sans perte de réponse.
>
> […] Propose d'abord un plan (3-6 lignes) avant de coder.

Puis :

> Je relance la demande pour la V1, merci de proposer un plan.

Après publication et validation du plan :

> Les points proposées sont validés tu peux lancer l'implémentation.

## Plan publié (commentaire `6728903799`)

1. Base V0 incluse (dépôt sans code) : modèles, migrations SQLite WAL, admin.
2. Import JSON validé, code de session + QR, salon d'attente, 1–4 questions
   colorées, couleur/symbole et graine persistés.
3. `ends_at` seule référence, auto-avance, pause/reprise/+temps/suivant/
   précédent.
4. Endpoints élève, refus tardif, doublon, `id_client`, file locale +
   backoff, accusé serveur, reconnexion.
5. Tableau protégé, compteurs temps réel, KaTeX + images.
6. Tests (minuteur, refus, doublon, reconnexion, anti-fuite), `ruff`,
   `JOURNAL.md` + ADR.

Points figés proposés : format `SPEC.md` §5 complété, tolérance 0 s,
4 couleurs + 4 symboles.

## Résultat

Succès : 86 tests passés, `ruff check .` OK, `makemigrations --check` OK,
application démontrée localement. Le détail est dans `JOURNAL.md`, les
décisions dans `docs/decisions/0001` à `0004`.

## Échecs / apprentissages

- Le premier jet de la palette utilisait la clé `texte` pour la couleur du
  texte ; le test anti-fuite l'a détectée comme une fuite potentielle de
  texte de choix. Renommage en `couleur_texte` : le test reste strict plutôt
  que d'être assoupli.
- Les listes de `Meta` (`ordering`, `constraints`, `indexes`) déclenchaient
  `RUF012` ; passage en tuples puis régénération de la migration initiale.
- Le dépôt vide a rendu la V0 nécessaire : le plan l'a rendu explicite et a
  été validé avant tout diff, conformément à `AGENTS.md` §0.
