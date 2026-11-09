# 0001 — Format d'import JSON V1

## Contexte

`docs/ROADMAP.md` classe « Format JSON d'import définitif » comme point ouvert
bloquant pour la V1. `docs/SPEC.md` §5 donne un format de départ et précise
qu'il est « à ajuster en V1 ».

## Options

1. Garder le format tel quel, avec `duree_s` par question.
2. Imposer un format par étapes (`etapes[]` contenant leurs questions).
3. Accepter un format libre et laisser l'admin corriger.

## Décision

Le format est celui de `SPEC.md` §5, complété et strictement validé :

- racine : `titre`, `questions[]` ;
- question : `uid`, `etape`, `duree_s`, `enonce`, `type`
  (`unique`/`multiple`), `choix[]`, `afficher_indice_multiple` optionnel ;
- choix : `lettre` (A–F), `texte`, `correct` (booléen), 2 à 6 choix ;
- `etape` numérotée 1..N sans trou ; 1 à 4 questions par étape ;
- toutes les questions d'une même étape portent la même `duree_s` ; la durée
  est stockée sur `Step`, pas sur `Question` ;
- `ordre` et `couleur_slot` sont dérivés de la position dans l'étape ;
- une question `unique` a exactement une bonne réponse, une question
  `multiple` en a au moins une.

L'import est transactionnel et disponible via
`python manage.py import_quiz <fichier> --proprietaire <utilisateur>`.
Les images sont ajoutées via l'admin (champ fichier), pas par le JSON.

## Conséquences

- Les erreurs sont explicites (champ, question concernée) et aucun QCM
  partiel n'est créé.
- Le format ne porte pas encore d'image ni de code ; l'admin reste la voie
  pour ces contenus.
- Un futur import plus riche (images, formules pré-rendues) devra passer par
  une nouvelle version du format, pas par une extension silencieuse.
