# 0011 — Banque de questions V3 (`QuestionSet`, sélection et import)

## Contexte

En V2, une `Question` appartenait à un seul `Quiz` et à une `Step` (paquet de
4). Réutiliser une question dans plusieurs QCM était impossible et l'import
créait directement des étapes. La V3 demande une banque de questions par
professeur, une sélection ordonnée par QCM et une interface d'import.

## Décision

- **`QuestionSet`** : banque nommée, rattachée à un professeur ; unicité
  `(proprietaire, nom)`. Une `Question` appartient à un seul ensemble et son
  `uid` est unique dans cet ensemble.
- **Sélection ordonnée** : `Quiz.questions` est un `ManyToMany` à travers
  `QuizQuestion` (`position`). La table de liaison est nécessaire pour
  conserver l'ordre choisi par le professeur et pour calculer les paquets ;
  elle évite une dépendance externe (`ordered-model`).
- **Étapes virtuelles** : `Question.quiz`, `Question.step`,
  `Question.couleur_slot` et le modèle `Step` sont supprimés. Les étapes sont
  recalculées à la volée à partir de la sélection (`generer_etapes`, paquets
  de 4). La couleur d'une question est sa position 1..T dans le paquet.
- **Durée** : `Quiz.duree_s` (défaut 60 s) est un plancher ; chaque étape
  générée dure `max(Quiz.duree_s, durées des questions du paquet)`. Une
  question complexe peut donc allonger l'étape, et le professeur peut fixer
  une durée minimale au QCM.
- **Data migration** (migrations `0010` → `0012`) : un ensemble
  « Questions existantes » est créé par professeur possédant des questions ;
  ses questions y sont rattachées, `QuizQuestion` reconstruit l'ordre des
  anciennes étapes, et `Quiz.duree_s` / `Question.duree_s` reprennent les
  durées d'étape. Les `uid` dupliqués entre anciens QCM sont suffixés
  `-<quiz_id>` pour respecter la nouvelle unicité.
- **Sélection dans l'admin** : le widget M2M standard n'est pas utilisé. Une
  page dédiée (`/admin/qcm/quiz/<id>/selection/`) liste les questions par
  ensemble avec des cases à cocher ; « Ajouter au Quiz » ajoute à la fin dans
  l'ordre soumis et ignore les doublons. La page du QCM affiche un bouton et
  un inline en lecture seule avec suppression.
- **Import** : JSON (`{"questions": [...]}`, racine liste acceptée) ou CSV
  « une ligne par choix » (`uid,enonce,type,lettre,texte,correct[,duree_s]`).
  La destination est un `QuestionSet` choisi dans le formulaire ; l'import est
  transactionnel et valide les choix, les bonnes réponses et les `uid`. La
  commande `import_quiz` reste disponible pour les anciens fichiers : elle
  crée un ensemble et un QCM qui sélectionne toutes les questions.

## Conséquences

- Les réponses (`Answer.question`) et les sessions existantes restent valides ;
  seules les lignes `Step` et les colonnes de rattachement au quiz disparaissent.
- Les tests et services lisent désormais `quiz.questions` ordonné par
  `QuizQuestion.position` ; `resultats.py` et l'API élève ne changent pas de
  contrat de sécurité (aucun énoncé, texte ou `est_correct` côté élève).
- L'ordre d'ajout au panier est conservé, mais il n'existe pas encore
  d'interface de réordonnancement manuel : on ajoute à la fin et on retire.
- `QuestionSet` est protégé : on ne supprime pas un ensemble qui contient
  encore des questions.
- Les champs `image` restent modifiables dans l'admin ; le CSV ne les importe
  pas.
