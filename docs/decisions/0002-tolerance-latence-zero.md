# 0002 — Tolérance de latence nulle

## Contexte

Le point ouvert V1 « Tolérance de latence sur les réponses proches de la fin »
n'était pas tranché. Une réponse peut arriver quelques millisecondes après
`ends_at` à cause du réseau ou du polling.

## Options

1. Tolérance de 0 s : `now() <= ends_at` accepte, `now() > ends_at` refuse.
2. Tolérance fixe de 1 à 2 s.
3. Accepter les réponses horodatées côté client avant `ends_at` (V3).

## Décision

Tolérance **0 s**, avec l'heure du serveur uniquement. La vérification est
faite au moment du traitement de `POST /api/repondre/`, sous verrou de la
séance. Aucune décision n'est prise à partir de l'horloge du téléphone.

## Conséquences

- Une réponse cliquée juste avant la fin mais reçue après `ends_at` est
  refusée ; le téléphone affiche « non prise en compte ».
- Le décompte local est uniquement indicatif et se resynchronise à chaque
  poll.
- La V3 pourra ajouter des réponses tardives horodatées avant la fin,
  signalées « à valider » au professeur, sans changer la règle par défaut.
