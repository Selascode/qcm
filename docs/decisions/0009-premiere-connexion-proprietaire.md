# 0009 — Première connexion propriétaire de l'appareil élève

- **Date** : 2026-11-11
- **Statut** : remplacé par l'ADR 0010 (cookie appareil httpOnly)
- **Décideur** : Selascode (validation du plan sur la PR #6)

## Contexte

La V2 sans PIN authentifie l'élève par son identifiant (`PRENOM-NOMnn`),
visible sur l'écran de pré-séance. Le join régénérait `jeton_appareil` à
chaque connexion : un second onglet/appareil avec le même identifiant
déconnectait le premier et prenait sa session — faille signalée avant le
merge. L'identifiant n'est pas un secret ; le PIN a été volontairement retiré.

## Décision

- **La première connexion est propriétaire** : `_rejoindre_groupe` conserve
  `jeton_appareil` ; une reconnexion n'est acceptée que si le client fournit
  le jeton existant (même appareil), sinon `409 deja_connecte`, sans exposer
  de jeton.
- **Le professeur libère l'appareil** : `reinitialiser_appareil` passe
  `jeton_appareil` à `NULL` (migration `0008`) ; l'ancien jeton reçoit 401 ;
  la prochaine connexion attribue un nouveau jeton. Le `Participant` et ses
  réponses sont conservés.
- **Le client** envoie le jeton stocké (clé `qcm.jeton.<code>`) pour le join
  groupe et affiche un message dédié.

## Conséquences

- Un second appareil ne peut plus prendre une session active ; le professeur
  récupère via « Réinitialiser ».
- L'identifiant reste public : une course à la toute première connexion reste
  possible sans secret ni PIN ; le reset professeur permet de corriger. Cette
  limite est assumée pour ne pas réintroduire de PIN.
- `SPEC.md` / `ARCHITECTURE.md` / `ROADMAP.md` ne sont pas modifiés par
  l'agent ; leur phrase « un nouvel appareil déconnecte l'ancien » devra être
  mise à jour par l'humain.
- Tests : `test_un_seul_appareil_actif`,
  `test_reconnexion_meme_jeton_garde_le_participant`,
  `test_autre_appareil_ne_peut_pas_piloter_le_premier`,
  `test_reset_prof_libere_lappareil`, `test_reinitialiser_l_appareil`.

## Références

- PR #6, faille signalée le 2026-11-11 et plan de 6 lignes validé.
- ADR 0008 (identifiants sans PIN).
