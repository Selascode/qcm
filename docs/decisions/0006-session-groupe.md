# 0006 — Rattachement d'une séance à un groupe

## Contexte

La V1 ne connaissait que des participants anonymes, créés à la connexion avec
le seul code de session. La V2 introduit de vrais élèves (`Student`), des
groupes (`Groupe`) et une authentification par identifiant + PIN. Il fallait
décider comment une séance sait quel groupe elle concerne, sans casser le mode
démo de la V1 (séance ouverte sans identifiants).

## Options

1. **Séance toujours rattachée à un groupe** : `Session.groupe` obligatoire.
   Simple à raisonner, mais casse la démo et les séances improvisées.
2. **`Session.groupe` nullable** : le professeur choisit un groupe à la
   création ; sans groupe, la séance reste libre (participants anonymes).
3. **Séance multi-groupes** : une séance peut accueillir plusieurs groupes.
   Plus souple, mais complexifie inutilement le filtrage et la page
   participants pour la V2.

## Décision

Option 2.

- Nouveau modèle `Groupe` (`nom` unique, `proprietaire`, `date_creation`).
- `Student.groupe` est obligatoire : un élève appartient à un seul groupe.
  La migration procède en trois temps : colonne nullable, data-migration de
  vérification, puis colonne obligatoire.
- `Session.groupe` est nullable (`SET_NULL`). Le professeur le choisit dans
  `/session/creer/` ; laisser vide crée une séance libre.
- Quand `Session.groupe` est défini, `/api/rejoindre/` exige
  `code_etudiant` + `pin` ; la page participants liste tout le groupe.
- Quand `Session.groupe` est `NULL`, la connexion reste anonyme (comme en V1)
  et la page participants liste les participants effectivement connectés.

## Conséquences

- Le mode démo de la V1 continue de fonctionner sans identifiants ; les tests
  V1 de connexion anonyme restent valides.
- Un élève ne peut pas rejoindre une séance d'un autre groupe : l'identifiant
  est recherché dans le groupe de la séance, et l'échec est générique.
- `Student.groupe` en `PROTECT` empêche de supprimer un groupe qui contient
  encore des élèves ; il faut d'abord les déplacer ou les supprimer.
- La page participants et `/api/etat_participants/` doivent gérer les deux cas
  (groupe complet vs participants connectés) : c'est fait dans
  `services.etat_participants`.
