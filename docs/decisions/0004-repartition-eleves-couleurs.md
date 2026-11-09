# 0004 — Répartition des élèves sur les questions d'une étape

## Contexte

Chaque élève a une couleur persistée et répond à la question qui porte sa
couleur. Une étape peut contenir 1 à 4 questions. Avec 1 à 3 questions,
toutes les couleurs n'ont pas de colonne correspondante : il faut décider ce
que font les élèves dont la couleur n'apparaît pas.

## Options

1. Seuls les élèves dont la couleur est présente répondent ; les autres
   attendent.
2. Réattribuer une couleur aléatoire à chaque étape.
3. Distribuer les élèves sur les questions présentes : la couleur sert
   d'index, replié modulo le nombre de questions de l'étape.

## Décision

Option 3 : dans une étape, les questions sont ordonnées (`ordre`, puis `id`)
et l'élève reçoit la question d'index `(couleur_assignee - 1) % nb_questions`.

- 4 questions : chaque couleur tombe sur sa colonne (comportement exact de la
  spec).
- 1 question : tous les élèves répondent à la même question.
- 2 ou 3 questions : les élèves sont répartis de façon déterministe et
  persistante.

Le téléphone reçoit et affiche la couleur et le symbole de la question à
traiter, pas ceux de la couleur « identitaire » de l'élève.

## Conséquences

- Aucun élève n'est laissé sans question, quel que soit le nombre de questions
  dans l'étape.
- Pour 2 ou 3 questions, la couleur affichée sur le téléphone peut différer
  de la couleur assignée à l'élève ; la couleur de la question est celle qui
  compte pour répondre au tableau.
- La répartition est recalculable après redémarrage : seules la couleur et la
  graine sont persistées, l'ordre des questions est stable.
