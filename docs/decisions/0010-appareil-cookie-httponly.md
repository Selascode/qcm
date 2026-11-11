# 0010 — Appareil élève identifié par cookie httpOnly

- **Date** : 2026-11-11
- **Statut** : accepté
- **Décideur** : Selascode (PR #6)
- **Remplace** : ADR 0009

## Contexte

L'ADR 0009 s'appuyait sur le jeton de session et `localStorage`. Or le
navigateur partage `localStorage` entre les onglets : un second onglet sur le
même appareil pouvait encore se connecter avec l'identifiant d'un autre élève
(`MARIE-DUP00` puis `PAUL-MAR00`). Le jeton doit être isolé par onglet, et
l'appareil identifié au niveau serveur, pas par le stockage partagé.

## Décision

- **Jeton par onglet** : le jeton de connexion élève est stocké dans
  `sessionStorage` (isolé par onglet) côté client ; il n'est plus dans
  `localStorage`.
- **Cookie appareil** : un cookie `cookie_appareil` httpOnly, UUID généré côté
  serveur, est partagé entre les onglets. `Participant.cookie_appareil`
  (nullable) le mémorise, avec la contrainte d'unicité
  `(session, cookie_appareil)`.
- **Join** :
  - cookie déjà associé à un autre `Participant` de la session →
    `409 appareil_deja_utilise` ;
  - même élève sur le même appareil (nouvel onglet) → accepté, le jeton de
    session existant est renvoyé ;
  - même élève sur un autre appareil → `409 deja_connecte`.
- **Reset professeur** : remet `jeton_appareil` et `cookie_appareil` à `NULL`
  et supprime le cookie de la réponse ; l'appareil est libéré et l'élève peut
  se reconnecter sans perdre ses réponses.

## Conséquences

- Un second élève ne peut plus se connecter depuis le même appareil, même
  dans un autre onglet ; le même élève peut se reconnecter dans un autre
  onglet.
- L'identifiant reste public et une course à la toute première connexion reste
  possible sans PIN ; le reset professeur permet de corriger. Cette limite est
  assumée pour ne pas réintroduire de PIN.
- `SPEC.md` / `ARCHITECTURE.md` / `ROADMAP.md` ne sont pas modifiés par
  l'agent ; leur phrase « un nouvel appareil déconnecte l'ancien » devra être
  mise à jour par l'humain.
- Tests : `test_un_seul_appareil_actif` (même appareil, autre élève refusé),
  `test_autre_appareil_ne_peut_pas_piloter_le_premier` (même élève, autre
  appareil refusé), `test_reset_prof_libere_lappareil` (cookie supprimé,
  appareil libéré), `test_reinitialiser_l_appareil`,
  `test_couleurs_round_robin_et_reconnexion` (un client HTTP par élève).

## Références

- PR #6, commentaire « Le correctif précédent n'a pas fonctionné… ».
- ADR 0009 (remplacé).
