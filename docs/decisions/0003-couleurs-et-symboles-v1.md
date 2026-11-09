# 0003 — Quatre couleurs et quatre symboles pour la V1

## Contexte

Le point ouvert V1 « Nombre de couleurs (4 ou 5) et jeu de symboles » devait
être figé. L'issue #1 limite une étape à 1–4 questions et demande que la
couleur et le symbole de l'élève soient persistés. La ROADMAP plaçait les
symboles en V2 (accessibilité), mais le périmètre V1 de l'issue les inclut
explicitement.

## Options

1. Cinq couleurs et cinq symboles, comme le suggérait `ARCHITECTURE.md`.
2. Quatre couleurs et quatre symboles, alignés sur le maximum de 4 questions
   par étape.
3. Couleurs sans symboles, en renvoyant l'accessibilité à la V2.

## Décision

Quatre couleurs, chacune avec un symbole :

| slot | couleur | hex | symbole |
| :--- | :--- | :--- | :--- |
| 1 | Rouge | `#C62828` | ● |
| 2 | Bleu | `#1565C0` | ▲ |
| 3 | Vert | `#2E7D32` | ■ |
| 4 | Violet | `#6A1B9A` | ◆ |

`Question.couleur_slot` ∈ {1..4}. `Participant.couleur_assignee` est tirée
au hasard et persistée. Le tableau et le téléphone affichent toujours le
symbole à côté de la couleur.

## Conséquences

- Une étape de 4 questions couvre exactement les 4 couleurs.
- Les étapes de 1 à 3 questions utilisent la répartition décrite dans l'ADR
  0004.
- Les symboles sont livrés dès la V1, conformément au périmètre de l'issue,
  même si la ROADMAP les listait aussi en V2.
- Le daltonisme ne dépend pas de la seule couleur.
