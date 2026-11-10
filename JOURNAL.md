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

## 2026-11-09 — Dette V1 : corrections d'interface et d'usage

**Objectif.** Traiter les 6 points du ticket #3 : fin de séance, accès iPhone
sur le Wi-Fi local, compteur du salon d'attente, QR uniquement sur la page
initiale, libellés français, colonne Groupe.

**Prompt / demande.** Issue #3 « Dette V1 : corrections d'interface et
d'usage » ; plan de 6 lignes publié (comment `6737768399`) et validé par
« Je valides tu peux lancer l'implémentation » (comment `6737809734`).

**Réalisé.**

- `terminer_session` + action `terminer` ; bouton « Terminer la séance » sur le
  tableau (retour à l'accueil) et sur l'écran final du téléphone ; lien de
  sortie sur les pages finales.
- `ALLOWED_HOSTS` : IPv4 locales détectées hors DEBUG ; section README « Accès
  depuis un téléphone » (même Wi-Fi, `runserver 0.0.0.0:8000`, URL IP, pare-feu).
- Compteur du nombre d'élèves connectés dans la zone d'attente du tableau,
  rafraîchi par le polling 1–2 s existant.
- Routes `/session/creer/` et `/session/<code>/` ; QR code déplacé sur cette
  page initiale, retiré du tableau ; lien « Créer une séance » sur l'accueil.
- `verbose_name`/`verbose_name_plural` français et test rendant les pages
  publiques et l'admin ; migration `0002_libelles_francais` limitée à
  `AlterModelOptions` et `AlterField`, sans SQL.
- Colonne « Groupe » (« — ») + TODO V2 dans l'admin Participants.

**Vérifications.** `pytest` (103 tests), `ruff check .`,
`manage.py check`, `makemigrations --check` ; captures avant/après dans la PR.

**Problèmes rencontrés / décisions.**

- La route `/session/creer/` n'existait pas : elle est ajoutée pour respecter
  « QR uniquement sur la page initiale » (ADR 0005).
- Le ticket interdit les migrations : seule une migration de métadonnées
  (`AlterModelOptions` et `AlterField`) a été générée pour les libellés, sans
  aucune opération de schéma ni changement de table.
- L'admin crée toujours des séances, mais le QR n'est accessible que via la
  page initiale `/session/<code>/` (lien documenté dans le README).

**Reste à faire.**

- Revue humaine et fusion manuelle (aucun auto-merge).
- Les cases V1 restantes de la ROADMAP et le tag `v1.0` restent à traiter
  après fusion.

## 2026-11-09 — Suivi de la PR #4 : tableau en pleine largeur

**Objectif.** Répondre à la revue : retirer la barre de droite du tableau pour
que les questions occupent toute la largeur, et rendre les compteurs de
réponses / participants discrets en pied de page.

**Réalisé.**

- Suppression de l'aside et de la colonne de 310 px ; `.tableau-app` passe à
  une colonne avec une ligne de pied de page.
- Compteurs déplacés dans un `pied-tableau` discret (petite police, centré en
  bas) ; compteur redondant du salon d'attente retiré ; JS mis à jour.
- Test du tableau adapté (plus d'aside, pied de page, aucun
  `nb-participants-attente`).
- Captures avant/après ajoutées dans `docs/screenshots/dette-v1/`.

**Vérifications.** `pytest` (103 tests), `ruff check .`, `manage.py check`,
`makemigrations --check`.

**Décision.** La demande humaine la plus récente prime sur la mise en avant du
compteur de salon d'attente : le compteur reste visible et rafraîchi, mais
discret en pied de page.

## 2026-11-09 — V2 : groupes, comptes élèves et notes

**Objectif.** Implémenter la V2 du ticket #5 : groupes, import CSV/JSON,
identifiants + PIN, un appareil actif, page participants, notation pure,
résultats et accessibilité.

**Prompt / demande.** Issue #5 « Implémente la V2 du projet QCM (comptes,
groupes et notes) ». Demande « Lis l'issue pour la V2 et propose d'abord un
plan (6-10 lignes) avant tout diff. Attends ma validation. » (comment
`6739163139`) ; plan de 10 lignes publié (comment `6739211714`) puis validé
par « Je valides tu peux démarer l'implémentation » (comment `6739251369`).

**Réalisé.**

- Modèles `Groupe`, `Student`, `Session.groupe`, `Participant.student` +
  `derniere_activite`, et barème `Quiz.penalite_active` /
  `Quiz.facteur_penalite` ; migrations nullable → vérification →
  non-nullable pour `Student.groupe` (ADR `0006-session-groupe.md`).
- `import_participants` (CSV/JSON, transactionnel, erreurs claires) et
  `liste_identifiants` (feuille HTML imprimable). Les PIN ne sont stockés
  qu'en hash ; le fichier d'identifiants en clair est ignoré par Git
  (ADR `0007-import-pdf-v3.md` pour le report du PDF,
  `0008-identifiants-et-pin.md` pour le stockage et la distribution).
- Authentification élève identifiant + PIN, message générique sans oracle,
  jeton régénéré à chaque connexion (ancien appareil → 401), bouton
  « Réinitialiser » côté prof.
- Page `/session/<code>/participants/` avec liste du groupe, statut
  « Connecté » irréversible au polling 1–2 s, compteur X/Y, cas
  `groupe = NULL` ; `/api/etat_participants/` sans PIN ni réponse.
- `notation.py` (`note_question`, `note_seance`) et vue `/resultats/`
  calculée à la volée (notes par élève avec plancher 0, taux de réussite par
  question).
- Accessibilité : symboles conservés sur téléphone et tableau, police Atkinson
  Hyperlegible en local (SIL OFL), contraste AA vérifié par test, cibles
  ≥ 44 px.

**Vérifications.** `pytest` : 169 tests passés (103 V1 + 66 V2).
`ruff check .`, `manage.py check`, `makemigrations --check` : OK. Captures
avant/après dans `docs/screenshots/v2/`.

**Problèmes / décisions.**

- `Student` n'existait pas dans le code V1 malgré `ARCHITECTURE.md` : le
  modèle est créé en V2 avec `Groupe`.
- `Session.groupe = NULL` conserve la connexion anonyme de la démo ; une
  séance avec groupe exige identifiant + PIN.
- Le `★` de la spécification n'est pas utilisé : le modèle plafonne à quatre
  questions par étape (quatre couleurs), un cinquième symbole n'aurait pas de
  question correspondante au tableau. Les quatre symboles ● ▲ ■ ◆ sont
  distincts et testés.
- Le PIN en clair n'existe que dans le fichier produit à l'import, à
  distribuer puis supprimer ; la base ne contient que `pin_hash`.

## 2026-11-09 — Suivi PR #6 : URL du QR code configurable

**Objectif.** Rendre l'URL encodée dans le QR code utilisable depuis un
téléphone (hôte LAN configurable) et afficher le QR + le code sur le tableau
en attente, pour que « Ouvrir » depuis l'admin soit directement utilisable.

**Prompt / demande.** Commentaires PR #6 : « Corrige l'URL encodée dans le QR
code de la page initiale de session… » puis « Parfait tu peux lancer le
correctif, fait en sorte que lorsqu'on fait "ouvrir" au niveau du tableau on
puisse avoir directement le qr code ainsi que le code qui s'affiche. »

**Réalisé.**

- `config/settings.py` : `QCM_LAN_HOST` lu depuis l'environnement (vide par
  défaut).
- `qcm/services.py` : helper `construire_url_rejoindre(request, session)` ;
  `http://<QCM_LAN_HOST>/rejoindre/<code>/` si défini, sinon
  `request.build_absolute_uri`.
- `/session/<code>/` : utilise le helper, affiche « URL encodée : … », et
  renvoie 403 à un autre professeur (au lieu de 404).
- Tableau en attente : QR code + code + URL encodée, le QR n'étant affiché
  qu'avant le démarrage.
- README section « Accès depuis un téléphone » : exemple `QCM_LAN_HOST`,
  rappel que `127.0.0.1` désigne le téléphone lui-même.
- Tests : sans variable, avec `192.168.1.42:8000`, variable vide, 403, et QR
  sur le tableau en attente.

**Vérifications.** `pytest` (174 tests), `ruff check .`, `manage.py check`,
`makemigrations --check`. Captures avant/après dans `docs/screenshots/qr-lan/`.

**Décision.** Le QR est réaffiché sur le tableau uniquement pendant l'attente
(mise à jour de l'ADR 0005) ; pendant la séance, il reste absent.

## 2026-11-10 — V2 corrigée : identifiants sans PIN, import web, rotation par blocs

**Objectif.** Appliquer les attendus V2 mis à jour : verbose names, import
`nom__iexact`, suppression du PIN et identifiants lisibles, import web,
rotation des questions par blocs, mode Présentation (timer à la même taille
que le tableau de base) et écran de pré-séance.

**Prompt / demande.** Issue #5, commentaire du 2026-11-10 « Implémente et
corrige la V2… » ; plan de 8 lignes (commentaire `6763671700`) validé avec la
précision « à la 5 le timer de l'écran présentation doit faire la même taille
que celui sur la page de base ».

**Réalisé.**

- Admin : `Student` → « Élève (Base) », `Participant` → « Élève (Session) » ;
  `import_participants` cherche le groupe avec `nom__iexact` ; tests d'import
  CSV/JSON avec un vrai groupe.
- Identifiants : suppression de `Student.pin_hash` (migration `0006`) ;
  identifiant `PRENOM-NOMnn` ; `/api/rejoindre/` n'accepte que
  `code_session` + `code_etudiant` ; un seul appareil (jeton écrasé) ;
  formulaire/JS sans PIN ; `liste_identifiants` retiré.
- Import web : `/groupe/<id>/importer-eleves/` (propriétaire), upload CSV/JSON,
  résumé, export CSV/JSON des identifiants ; lien depuis l'admin Groupe.
- Répartition : `qcm/services.py` converti en paquet ; helper
  `repartition.py::generer_etapes` ; `Step` = paquet (pas de duplication de
  `Question`) et étapes virtuelles ; couleur
  `(couleur initiale + étape dans le paquet)` ; l'import JSON regroupe par 4 ;
  tests N=10 → 10 étapes, N=5 → 5.
- Mode Présentation : `/tableau/<code>/presentation/` (questions + timer +
  compteurs, sans contrôles) ; timer de la même taille que le tableau de base ;
  bouton sur le tableau.
- Accueil : « Créer une séance » réservé aux profs (test) ; page participants
  conforme (Nom, Prénom, Identifiant, Statut).
- README et ADR 0008 alignés sur l'absence de PIN.

**Vérifications.** `pytest` (189 tests), `ruff check .`, `manage.py check`,
`makemigrations --check`. Captures avant/après à ajouter dans la PR.

**Décisions.** `Step` reste une ligne par paquet : les étapes virtuelles sont
calculées, ce qui évite de dupliquer `Question` (uid unique par quiz). Le PIN
est retiré : l'identifiant est visible sur l'écran de pré-séance et un
nouvel appareil remplace l'ancien. Le timer de la présentation reprend
exactement la taille du timer du tableau de base (demande humaine).


