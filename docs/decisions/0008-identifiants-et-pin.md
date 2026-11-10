# 0008 — Identifiants élèves lisibles, sans PIN

> Cette version remplace l'ADR initial qui prévoyait un PIN haché et une liste
> imprimable de PIN. La revue du 2026-11-10 a retiré le PIN du périmètre V2.

## Contexte

La V2 doit identifier chaque élève pour l'authentifier à une séance. Un premier
projet utilisait un identifiant + un PIN haché, imposant une feuille de PIN à
distribuer et un mécanisme de secours (`--regenerer`). La revue a simplifié :
l'identifiant est lisible et affiché sur l'écran de pré-séance ; un second
secret n'apporte pas de sécurité réelle dans une salle de classe (l'élève est
devant le professeur) et complique l'import et la distribution.

## Options

1. **PIN haché + liste imprimable** : plus de secret, mais stockage/diffusion
   de PIN à gérer, commande `liste_identifiants`, régénération, risque de
   perte.
2. **Identifiant lisible seul** : `PRENOM-NOMnn` (ex. `MARIE-DUP32`), unique,
   visible sur l'écran de pré-séance ; un seul appareil actif ; le professeur
   peut réinitialiser l'appareil.
3. **Compte élève complet avec mot de passe** : hors périmètre V2 (pas de
   récupération de mot de passe, pas de compte en libre-service).

## Décision

Option 2.

- L'import génère un identifiant lisible et unique
  (`qcm/import_participants.py::generer_code_etudiant`) ; `Student.pin_hash`
  est supprimé par la migration `0006`.
- `/api/rejoindre/` n'accepte que `code_session` + `code_etudiant` pour une
  séance avec groupe ; la démo `groupe = NULL` reste anonyme.
- Une nouvelle connexion avec le même identifiant écrase `jeton_appareil` ;
  l'ancien appareil reçoit `401`. Le professeur peut réinitialiser l'appareil
  depuis la page participants.
- L'export CSV/JSON des identifiants (sans PIN) est fourni par l'interface
  d'import `/groupe/<id>/importer-eleves/` ; la commande `liste_identifiants`
  (PIN) est retirée.

## Conséquences

- Plus de feuille de PIN à distribuer ni à supprimer : la liste des
  identifiants est le document de référence.
- L'identifiant n'est pas un secret ; il est visible sur l'écran de
  pré-séance. La protection repose sur le remplacement d'appareil et la
  réinitialisation par le professeur, pas sur un secret partagé.
- La migration supprime une colonne qui n'est plus utilisée ; aucune donnée
  métier (réponses, groupes) n'est touchée.
- L'ADR 0008 initial est remplacé ; le README, le JOURNAL et les tests sont
  alignés sur l'absence de PIN.
