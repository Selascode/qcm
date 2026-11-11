# 0012 — Identifiant INSA, saisie papier et exports CSV

## Contexte

La fin de la V3 doit rendre les résultats exploitables par l'INSA : un
identifiant fourni par l'école en plus du code de connexion généré, un accès
direct aux résultats depuis l'admin des séances, une saisie des copies papier
pour les élèves absents de l'application, et deux exports CSV ouvrables dans
Excel. Le formulaire Django standard d'ajout d'une `Answer` est trop lent
lorsque plusieurs élèves ont rendu une copie papier.

## Décision

- **`Student.identifiant_insa`** : `CharField(max_length=32, unique=True,
  null=True, blank=True)`, distinct de `code_etudiant` qui reste l'identifiant
  de connexion. Une valeur vide est normalisée en `NULL` (plusieurs élèves
  peuvent donc ne pas avoir d'identifiant INSA sans violer l'unicité). L'import
  CSV/JSON des élèves accepte une colonne `identifiant_insa` facultative et
  refuse les doublons (dans le fichier et en base) avec un message lisible.
- **Accès aux résultats** : `SessionAdmin` affiche une colonne « Résultats »
  avec le lien « Voir les résultats » pour une séance en cours ou terminée. Le
  lien réutilise la route existante `/resultats/<code_session>/` : le code de
  séance est déjà l'identifiant public stable utilisé par le tableau, les
  participants et les QR codes ; ajouter `/resultats/<session_id>/` aurait
  dupliqué deux routes pour la même page. Le tableau affiche désormais
  « Voir les résultats ».
- **Note sur 20** : le total brut (somme des notes de questions, plancher 0)
  reste affiché, et une colonne « Note /20 » le ramène à l'échelle du nombre de
  questions : `total / nb_questions × 20`. La note n'est jamais stockée.
- **Saisie papier dans l'admin** : `AnswerAdmin` autorise l'ajout (modification
  toujours interdite), propose `source = "papier"` par défaut, déduit la
  séance du participant et génère l'`id_client`. Le formulaire refuse toute
  création si une réponse existe déjà pour `(participant, question)` ; le
  message précise que l'application prime.
- **Vue groupée `/session/<code>/saisie-papier/`** : réservée au professeur
  propriétaire. Le professeur choisit un élève du groupe (participant ou non),
  saisit toutes les réponses sur une page (boutons radio pour les questions
  uniques, cases à cocher pour les questions multiples) et enregistre en une
  fois. Le `Participant` est créé s'il manque, avec la couleur Round-Robin. Les
  réponses `app` sont affichées verrouillées et ne sont jamais modifiées ; une
  réponse papier existante est mise à jour. L'élève peut aussi être recherché
  par `code_etudiant` ou `identifiant_insa` : le participant est créé et
  l'élève est sélectionné.
- **Import CSV papier** : `identifiant,uid_question,lettre_choisie`, en UTF-8
  (BOM accepté), séparateur virgule. L'identifiant peut être le code de
  connexion ou l'identifiant INSA. Une question multiple accepte plusieurs
  lettres dans la cellule (`AC` ou `A C`). Toutes les lignes sont validées avant
  écriture ; l'import est transactionnel. Une ligne dont la réponse existe déjà
  avec `source="app"` est ignorée (l'application prime), une réponse papier
  existante est mise à jour, et les participants manquants sont créés.
- **Exports CSV** : deux boutons sur la page des résultats, `utf-8-sig` (BOM)
  et virgule pour Excel. L'export « notes » contient `Nom, Prénom, Identifiant,
  Note /20`, puis une colonne par question (uid) avec les lettres cochées.
  L'export « détail » contient une ligne par élève et par question avec
  l'énoncé court, la réponse donnée, la bonne réponse et les points obtenus.
  L'identifiant exporté est `identifiant_insa` s'il existe, sinon
  `code_etudiant`.
- **Migration** : `0013_student_identifiant_insa` ajoute uniquement la colonne ;
  aucune donnée existante n'est modifiée.

## Conséquences

- Les copies papier peuvent être saisies sans créer de compte élève
  supplémentaire : le participant papier utilise le même modèle et pourra
  ensuite se connecter à l'application ; son cookie sera rattaché à la
  connexion.
- Les exports ne stockent rien : toute correction d'une réponse se répercute
  immédiatement dans les notes et les taux de réussite.
- Une question multiple papier peut enregistrer plusieurs lettres ; une
  question unique n'en accepte qu'une. Le CSV papier reprend cette règle.
- Les relevés de notes utilisent le code de connexion pour les élèves sans
  identifiant INSA ; aucune colonne INSA vide n'est inventée.
- Le PDF personnalisé par élève (WeasyPrint) reste hors de ce ticket.
