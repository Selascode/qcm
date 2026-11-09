# 0008 — Identifiants élèves, PIN hachés et liste imprimable

## Contexte

La V2 doit authentifier chaque élève par un identifiant et un PIN à 4–6
chiffres, tout en produisant une liste imprimable remise individuellement.
Stocker le PIN en clair en base est exclu. Mais `liste_identifiants` doit
afficher le PIN : un hash seul ne permet pas de le retrouver.

## Options

1. **Stocker le PIN en clair** dans `Student` : simple, mais contraire à la
   règle « hash, pas de stockage en clair ».
2. **Ne stocker que le hash et régénérer les PIN à chaque impression** :
   chaque impression invalide les feuilles précédentes, ce qui est dangereux
   une fois les feuilles distribuées.
3. **Stocker le hash en base et écrire les PIN en clair dans un fichier
   d'identifiants au moment de l'import**, à distribuer puis supprimer. Le
   fichier est ignoré par Git ; la base ne contient que le hash.

## Décision

Option 3.

- `import_participants` génère identifiant + PIN, stocke
  `make_password(pin)` dans `Student.pin_hash` et écrit
  `identifiants_<groupe>.json` (chemin surchargeable par `--identifiants`).
- `liste_identifiants` relit ce fichier et produit une feuille HTML
  imprimable ; elle ne peut pas retrouver un PIN perdu.
- `liste_identifiants --regenerer` régénère tous les PIN du groupe, met à jour
  les hashes et réécrit le fichier. C'est la seule procédure de secours si le
  fichier est perdu ; elle invalide les anciennes feuilles.
- Le fichier `identifiants_*` est ajouté à `.gitignore` et doit être supprimé
  après impression.

## Conséquences

- La base ne permet pas de reconstituer un PIN ; c'est voulu.
- La liste imprimable est le seul document contenant les PIN en clair. Sa
  manipulation est de la responsabilité du professeur.
- Le bouton « Réinitialiser » de la page participants ne change pas le PIN :
  il régénère seulement le jeton d'appareil (`Participant.jeton_appareil`).
