# JOURNAL — QCM en direct

## 2026-11-09 — V1 : séance complète avec redémarrage serveur

**Objectif.** Implémenter le périmètre V1 du ticket #1 : import JSON, code de
session + QR, séance de 5 étapes avec 1 à 4 questions colorées, contrôles
professeur, reconnexion et file locale, sans perte de réponse après
redémarrage.

**Prompt / demande.** Issue #1 « @Selascode-agent Implémente la V1 du projet
QCM » puis relance « Je relance la demande pour la V1, merci de proposer un
plan. » (comment `6728877448`). Plan de 6 lignes publié dans l'issue
(comment `6728903799`), validé par « Les points proposées sont validés tu peux
lancer l'implémentation. » (comment `6728947045`), avec les trois défauts :
format JSON `SPEC.md` §5, tolérance de latence 0 s, 4 couleurs + 4 symboles.

**Réalisé.**

- Projet Django `config/` + application `qcm/`, SQLite WAL, admin complet
  (`Quiz`, `Step`, `Question`, `Choice`, `Session`, `Participant`, `Answer`).
- Import JSON transactionnel (`manage.py import_quiz`) et fichier de démo
  `examples/quiz_demo.json` (5 étapes, 10 questions, KaTeX).
- Services de séance : démarrage, auto-avance idempotente sur `ends_at`,
  pause, reprise, +temps, suivant, précédent, sous verrou.
- Endpoints élève `/api/rejoindre/`, `/api/etat/`, `/api/repondre/` et
  endpoints prof `/api/etat_prof/`, `/api/piloter/`.
- Pages : accueil, saisie de code, connexion, téléphone (file locale,
  backoff, polling 1–2 s), tableau professeur (QR, compteurs, KaTeX).
- Tests : import, invariants du modèle, anti-fuite, refus tardif, doublon,
  `id_client`, reconnexion, timer, pilotage/auth/CSRF, et le parcours V1 de
  5 étapes avec redémarrage simulé.

**Vérifications.** `pytest` : 87 tests passés. `ruff check .` : OK.
`python manage.py makemigrations --check` : OK. Démonstration locale avec le
QCM de démo et captures d'écran (tableau, téléphone). File locale vérifiée de
bout en bout : serveur coupé, clic, « En attente du réseau… », serveur
redémarré, « Votre réponse a bien été reçue. » et file vidée.

**Problèmes rencontrés / décisions.**

- Le dépôt ne contenait que `AGENTS.md` et `docs/` : la base V0 (modèles,
  admin, pages, timer) a été incluse dans la V1, avec accord du plan.
- 4 couleurs et 4 symboles (ADR 0003). Pour 1 à 3 questions par étape, la
  couleur est repliée modulo le nombre de questions afin que chaque élève ait
  toujours une question (ADR 0004). Le téléphone affiche la couleur de la
  question à traiter.
- Tolérance de latence nulle (ADR 0002) ; format JSON figé (ADR 0001).
- Le test anti-fuite a révélé que la clé `texte` de la palette de couleurs
  (couleur du texte) était confondue avec le `texte` des choix. La clé a été
  renommée `couleur_texte` : le test de sécurité reste strict.
- La migration initiale a été régénérée après passage des listes de `Meta`
  en tuples (exigence `ruff`), pour éviter une migration cosmétique.

**Reste à faire / points ouverts.**

- Revue humaine et fusion manuelle (aucun auto-merge).
- `docs/ROADMAP.md` n'a pas été modifiée (AGENTS.md §7) : les cases V1 et le
  point « 4 ou 5 couleurs » restent à cocher/trancher côté humain.
- `docs/SPEC.md` §11 mentionne « 1 à 5 questions colorées » alors que §3 et
  l'issue disent 1 à 4 ; l'implémentation suit 1 à 4. À corriger dans une PR
  doc dédiée (SPEC non modifiée ici).
- Le tag Git `v1.0` est à créer après fusion.
