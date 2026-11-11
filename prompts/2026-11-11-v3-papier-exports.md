# Prompt du 2026-11-11 — Fin de la V3 : INSA, résultats, papier, exports

## Demande

Issue #9 :

> @Selascode-agent Implémente la fin de la V3 : identifiants INSA, résultats
> depuis l'admin, saisie papier et exports CSV.
>
> Lis AGENTS.md, docs/SPEC.md et docs/ARCHITECTURE.md. Propose un plan de 6-8
> lignes avant de coder. Périmètre fermé. Pas de nouvelle dépendance non
> justifiée.
>
> 0. `Student.identifiant_insa` facultatif, unique, distinct de
>    `code_etudiant` ; import CSV/JSON et migration.
> 1. Colonne « Résultats » dans l'admin des séances et bouton sur le tableau ;
>    page de résultats avec notes par élève (plancher 0) et taux par question.
> 2. Saisie manuelle des réponses papier dans l'admin `Answer`, `source=papier`
>    par défaut, refus si une réponse app existe.
> 3. Deux exports CSV : notes par élève (INSA ou code, note /20, une colonne
>    par question) et détail par question ; UTF-8 avec BOM et virgule.
> 4. Tests : INSA optionnel, lien résultats depuis l'admin, en-tête/BOM/note
>    sur 20, refus d'une réponse papier si une réponse app existe.

Puis, après validation du plan :

> Le plan est validé sur la structure (modèle, exports, résultats).
> Cependant, la section 4 (Saisie papier) n'est pas assez ergonomique...
>
> 1. Vue de saisie groupée `/session/<code>/saisie-papier/` : choix d'un élève
>    dans une liste, formulaire de toutes les questions, enregistrement en un
>    clic, création automatique du `Participant` s'il manque.
> 2. Ajout rapide : recherche d'un élève par identifiant dans `Student` et
>    liaison à la session.
> 3. Import CSV de réponses papier `identifiant, uid_question, lettre_choisie`,
>    transactionnel, avec la règle « l'appli prime ».
>
> Propose un plan de 3 lignes sur ces ajouts, puis lance l'implémentation.

## Plans publiés

- Plan V3 de 8 lignes : commentaire `6805844438` (issue #9).
- Plan des 3 ajouts de saisie papier : commentaire `6805989205`.

## Résultat

- `Student.identifiant_insa` (migration `0013`), import CSV/JSON et admin.
- Lien « Voir les résultats » dans l'admin des séances et sur le tableau ;
  note /20 sur la page des résultats.
- Exports CSV notes/détail en `utf-8-sig`, séparateur virgule, testés.
- Saisie papier groupée, liaison rapide par code ou identifiant INSA, import
  CSV transactionnel ; l'application prime toujours.
- Tests dédiés et non-régression complète, `ruff`, `manage.py check`,
  `makemigrations --check`.
- ADR 0012, JOURNAL, README et captures avant/après.
