# Prompt du 2026-11-11 — V3 : banque de questions et import

## Demande

> @Selascode-agent Lance la V3 : Refonte des questions en Banque de questions
> (QuestionSet) et interface d'import.
>
> Lis AGENTS.md, docs/SPEC.md, docs/ARCHITECTURE.md et docs/ROADMAP.md
> (section V3). Ce ticket implique une modification de la base de données : tu
> DOIS inclure une data-migration pour ne perdre aucune question existante.
> Propose un plan détaillé de 6-8 lignes avant de coder.
>
> 1. Modèle `QuestionSet` (nom, propriétaire FK User), FK `set` sur `Question`,
>    data migration vers un ensemble par défaut par professeur.
> 2. Refonte de `Quiz` : champ `questions` ManyToMany, `generer_etapes()` sur
>    cette sélection.
> 3. Interface d'import de questions JSON/CSV avec choix du set et résumé.
> 4. Admin : ensembles d'abord, puis questions ; sélection des questions pour
>    un Quiz.
> 5. `generer_etapes(questions, max_par_etape=4)` et rotation des couleurs.
> 6. Tests : data migration, import, Quiz de 5 questions de sets différents.

Puis, après validation du plan :

> Le plan technique est validé. J'accepte ta proposition concernant la durée
> (`Quiz.duree_s`). Cependant, avant de lancer l'implémentation, j'ai deux
> précisions à ajouter :
>
> 1. **Durée par défaut** : implémente `Quiz.duree_s` (défaut 60 s), ajoute
>    aussi un champ `duree_s` sur `Question` pour moduler la durée d'une
>    question complexe, et que le quiz prenne la durée de la question la plus
>    longue.
> 2. **Interface de sélection** : le widget M2M standard (Ctrl+Clic) est
>    inutilisable. Créer une interface « Panier » : bouton « Sélectionner les
>    questions » sur la page du Quiz, page groupée par QuestionSet avec cases à
>    cocher, « Ajouter au Quiz » en conservant l'ordre via `QuizQuestion`, et
>    liste des questions sélectionnées avec possibilité de les retirer.
>
> Les autres points sont validés. Lance un plan de 3 lignes sur l'interface de
> sélection, puis commence l'implémentation.

## Plans publiés

- Plan V3 de 8 lignes : commentaire `6803586456` (issue #7).
- Plan de 3 lignes du panier : commentaire `6803790142`.

## Résultat

- Modèles V3, migrations `0010`–`0012` avec data migration testée.
- Import JSON/CSV dans un `QuestionSet`, page web et commande `import_quiz`
  adaptée.
- Panier admin groupé par ensemble, ordre conservé, doublons ignorés,
  suppression depuis la page du QCM.
- Étapes virtuelles, couleurs calculées et durées `Quiz.duree_s` /
  `Question.duree_s`.
- 216 tests verts, `ruff`, `manage.py check`, `makemigrations --check`.
- PR avec captures avant/après dans `docs/screenshots/v3/`, ADR 0011 et
  JOURNAL.
