# 0005 — Page initiale de session et fin de séance explicite

## Contexte

La V1 affichait le QR code sur le tableau, y compris pendant la séance. La fin
de séance (auto-avance ou bouton « Suivant ») laissait le professeur et l'élève
sur un écran sans action. Les séances étaient créées uniquement dans l'admin ;
la route `/session/creer/` évoquée par le ticket #3 n'existait pas encore.

## Options

1. Garder le QR code sur le tableau et ajouter un simple lien de retour sur la
   page finale.
2. Déplacer le QR code sur une page initiale dédiée, créée après
   `POST /session/creer/`, et ajouter une action explicite de clôture.
3. Supprimer le QR code et le remplacer par la seule saisie du code.

## Décision

Option 2 :

- ajout de `/session/creer/` (choix du QCM, puis `POST` de création) et de
  `/session/<code>/`, la page initiale qui affiche le code, le QR code et le
  lien vers le tableau ;
- le QR code n'est rendu que par cette page et retiré du tableau, de l'accueil
  et du téléphone ;
- ajout de `terminer_session` et de l'action `terminer`, avec un bouton
  « Terminer la séance » sur le tableau (retour à l'accueil du professeur) et
  sur l'écran final du téléphone (retour à l'accueil).

## Conséquences

- Une interface professeur minimale (création de séance) est ajoutée avant la
  V2 : c'est une dérogation assumée à `ARCHITECTURE.md` §5, limitée à ce
  parcours.
- Le QR code n'est plus visible pendant la séance ; le professeur garde la page
  initiale ouverte ou revient par `/session/<code>/`.
- La fin de séance est explicite et ne bloque plus ni le professeur ni l'élève.
- L'admin reste utilisable pour créer une séance ; la page initiale reste
  accessible par URL.
