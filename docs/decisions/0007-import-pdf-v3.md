# 0007 — Import PDF de la liste des participants repoussé en V3

## Contexte

La V2 doit importer une liste d'élèves pour créer les comptes (identifiant +
PIN). Le format réellement fourni par l'administration est souvent un PDF
(tableau de classe). L'issue V2 demandait un import CSV et JSON, et laissait le
PDF hors périmètre, avec une ADR à produire.

## Options

1. **Implémenter le PDF en V2** : extraction de texte puis parsing de tableaux.
   Nécessite une dépendance (par exemple `pypdf`) et un gabarit PDF stable.
   Les tableaux PDF sont fragiles : colonnes fusionnées, en-têtes variables,
   accents et ligatures.
2. **Reporter le PDF en V3** et couvrir le besoin avec CSV + JSON.
   L'enseignant exporte la liste depuis l'outil de scolarité en CSV, ou la
   convertit une fois en JSON.
3. **Saisie manuelle via l'admin** : possible, mais l'admin des élèves est en
   lecture seule pour protéger `pin_hash` ; la saisie manuelle de PIN hachés
   n'est pas acceptable.

## Décision

Option 2 : le PDF est explicitement hors périmètre V2. `import_participants`
accepte `.csv` (en-tête `nom`, `prenom`) et `.json` (liste d'objets). Une
extension inconnue produit une erreur claire.

Le PDF pourra être rouvert en V3 si le professeur fournit un gabarit stable ;
il faudra alors une dépendance justifiée et épinglée dans `requirements.txt`.

## Conséquences

- Aucune nouvelle dépendance n'est ajoutée en V2.
- L'import reste transactionnel et validé avant écriture (en-tête, doublons,
  lignes vides, groupe inconnu).
- La liste imprimable (`liste_identifiants`) est produite en HTML à partir du
  fichier d'identifiants créé à l'import ; les PIN ne sont jamais stockés en
  clair dans la base.
