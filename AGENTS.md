# AGENTS.md — Règles du projet QCM en direct (PAO INSA Rouen)

Ce fichier est **impératif**. Il prime sur toute habitude de l'agent.
En cas de doute ou de conflit avec une instruction d'un ticket : **demander**, ne pas improviser.

La spécification complète est dans `docs/SPEC.md`. L'architecture dans `docs/ARCHITECTURE.md`.
La version en cours et les cases à cocher dans `docs/ROADMAP.md`.

---

## 0. Règle d'or

**Propose d'abord un plan, code ensuite.** Aucun diff sans plan validé (même court : 3 à 6 lignes).
Un ticket = une branche = un périmètre fermé. Si le ticket est ambigu, poser une question dans l'Issue plutôt que de deviner.

---

## 1. Sécurité — règles non négociables

Ces règles sont la raison d'être du projet. Une violation = le ticket est refusé, même si les tests passent.

1. **Aucun énoncé, texte de choix ou champ `est_correct` ne doit jamais partir vers un téléphone élève.**
   - Les endpoints élèves (`/etat/`, `/repondre/`, etc.) ne renvoient que : couleur de la question, nombre de choix, temps restant, accusé de réception, statut de la réponse.
   - Tout nouveau champ ajouté à une réponse JSON destinée à l'élève doit être justifié dans le plan.
2. **La note est calculée uniquement côté serveur.** Jamais dans le navigateur, jamais renvoyée à l'élève avant la fin de la séance (sauf si le prof a activé les stats élèves).
3. **L'heure de référence est toujours celle du serveur.** `ends_at` est stocké en base. Le client ne fait qu'afficher un décompte local à partir de l'heure serveur. Aucune décision d'acceptation/refus d'une réponse ne se prend côté client.
4. **Une réponse reçue après `ends_at` est refusée.** Une seconde réponse à la même question est refusée (contrainte unique `(participant, question)`).
5. **Chaque ticket qui touche un endpoint élève doit être accompagné d'un test** qui parcourt le JSON de réponse et échoue si `enonce`, `texte` (des choix), ou `est_correct` apparaît.

---

## 2. Stack figée

Ne pas ajouter, retirer ou remplacer une brique sans accord explicite dans l'Issue.

- **Backend** : Django + Python, **ORM uniquement** (pas de SQL brut).
- **Front** : templates Django + **HTMX** + JavaScript simple. Pas de framework JS (React, Vue, Svelte…).
- **Formules** : KaTeX (côté tableau uniquement).
- **Base** : SQLite en mode WAL pour le dev/démo ; PostgreSQL pour l'école. Le code doit rester compatible ORM avec les deux.
- **Temps réel** : **polling** d'un endpoint léger `/etat/` toutes les 1 à 2 s avec délai aléatoire. **Pas de SSE, pas de Channels, pas de WebSockets** sauf si un test de charge prouve que le polling ne suffit pas (et dans ce cas, en parler d'abord).
- **Tests** : `pytest` + `pytest-django`.
- **Style** : `ruff` (config par défaut du dépôt).

Toute nouvelle dépendance doit être :
- justifiée dans le plan du ticket (pourquoi la stdlib ou l'existant ne suffit pas) ;
- ajoutée à `requirements.txt` avec une version épinglée ;
- signalée dans le résumé de la PR.

---

## 3. Modèle de données — invariants

Le schéma de référence est dans `docs/ARCHITECTURE.md` (section « Modèle de données »). Points à ne pas casser :

- `Answer` a une **contrainte unique `(participant, question)`**. Ne jamais la retirer.
- `Answer` porte `source` (`app` / `papier`) et `id_client` (anti-doublon). Ne pas les supprimer.
- `Session.ends_at` est la **seule** référence temporelle. Pause et ajout de temps modifient `ends_at`.
- `Participant.graine_mélange` et `Participant.couleur_assignée` sont **persistés** : on doit pouvoir reconstituer l'ordre des boutons et la couleur d'un élève après redémarrage.
- `Question.uid` est unique **par quiz**, pas globalement.
- La durée est portée par `Step`, pas par `Question`.

Toute migration qui touche à ces invariants doit être justifiée dans la PR.

---

## 4. Barème — fonction pure, configurable, testée

Le barème ne doit **jamais** être stocké en base ni dupliqué dans une vue.
Il est calculé par des fonctions pures (par exemple `notation.py::note_question(...)` et
`notation.py::note_seance(...)`) qui reçoivent **explicitement** leur configuration en
paramètre (pas de constante globale, pas de lecture de la base dans la fonction).

### Règles métier (non négociables)

1. **Pénalité optionnelle** : le professeur peut activer ou désactiver la pénalité pour
   les mauvaises réponses. Quand elle est désactivée, une mauvaise réponse ne retire
   aucun point (elle contribue à `0`, pas à `−1`).
2. **La note d'une question peut être négative.** Elle est bornée entre
   `−facteur_penalite` et `1`. Aucun plancher à `0` au niveau de la question.
3. **Seule la note finale de la séance est plafonnée à 0.** La somme des notes de
   questions est calculée sans plancher, puis `note_finale = max(0, somme)`. Un élève
   peut donc avoir `−0.5` sur une question et une note finale `0`.
4. **Pondération partielle** :
   `note_question = (bonnes cochées − facteur_penalite × mauvaises cochées) / nombre de bonnes réponses`,
   bornée entre `−facteur_penalite` et `1`.
5. **Pas de réponse** = `0` pour cette question.

### Signatures attendues

```python
def note_question(
    choix_selectionnes: list[str],
    question: Question,
    *,
    penalite_active: bool = True,
    facteur_penalite: float = 1.0,
) -> float:
    """Note d'une question, bornée entre -facteur_penalite et 1. Ne lit pas la base."""

def note_seance(
    notes_questions: list[float],
) -> float:
    """Note finale d'une séance : max(0, somme). Ne lit pas la base."""

---

## 5. Processus par ticket

1. **Lire** le ticket, `docs/SPEC.md` et la section concernée de `docs/ARCHITECTURE.md`.
2. **Écrire un plan court** dans l'Issue (objectif, fichiers touchés, critères d'acceptation, hors périmètre).
3. **Créer la branche** `agent/<nom-du-ticket>` (le worktree est déjà créé par `dsh-superagent`).
4. **Écrire ou compléter les tests d'abord** quand c'est pertinent (notation, timer, refus tardif, absence d'énoncé).
5. **Implémenter** en petits diffs relisibles (< 10 minutes de lecture).
6. **Lancer** `pytest` et `ruff`. Ne pas pousser si ça échoue.
7. **Ouvrir la PR** avec : résumé, critères d'acceptation cochés, points ouverts, et mention explicite de toute dépendance ajoutée.
8. **Ne jamais merger** : la fusion est manuelle, faite par un humain (`Selascode`). Pas d'auto-merge, pas de `--force-push` sur une branche partagée.

---

## 6. Documentation obligatoire

- **`JOURNAL.md`** : une entrée par session (date, objectif, prompt utilisé, résultat, problème, décision). C'est la matière du rapport PAO, pas un bonus.
- **`docs/decisions/NNNN-titre.md`** : pour tout choix structurant (contexte, options, décision, conséquences). Le format ADR est attendu.
- **`prompts/`** : un fichier par prompt clé, avec le résultat (succès **et** échecs). Les échecs sont valorisés, pas cachés.
- Une fonctionnalité terminée = un tag Git (ex. `v0.1`, `v1.0`).

---

## 7. Ce que l'agent ne doit pas faire

- Créer une fonctionnalité non demandée dans le ticket (« tant qu'on y est, j'ai ajouté… »).
- Réécrire un fichier entier pour corriger trois lignes.
- Changer le barème, le schéma de `Answer`, ou la politique de polling sans ticket dédié.
- Ajouter un `print` de debug dans le code poussé.
- Modifier `AGENTS.md`, `docs/SPEC.md` ou `docs/ROADMAP.md` sans instruction explicite.
- Toucher à la configuration `dsh-superagent` (profil, policy, executor) : ce n'est pas le périmètre du code applicatif.
- Utiliser `git push --force` sur `main` ou sur une branche déjà en PR.

---

## 8. Critères de « terminé » par version (rappel)

| Version | Critère mesurable |
| :--- | :--- |
| **V0** | 3 téléphones rejoignent, répondent, le prof voit les réponses, une réponse tardive est refusée. |
| **V1** | Séance de 5 étapes avec redémarrage serveur au milieu, aucune réponse perdue. |
| **V2** | Calcul des notes couvert par des tests ; taux de réussite par question exact. |
| **V3** | Une feuille papier saisie + une séance appli fusionnent sans doublon. |
| **V4** | Test de charge à 100 clients simulés sans erreur ; guide remis au professeur. |

Un ticket qui ne fait pas avancer un de ces critères est probablement hors périmètre : le signaler.

---

## 9. En cas de blocage

- Reformuler le problème dans l'Issue avant de coder au hasard.
- Si une correction s'enlise (2 tentatives échouées), **revenir en arrière** (`git reset` sur la branche) et proposer une autre approche dans l'Issue.
- Ne pas empiler les correctifs sur un code douteux : préférer un petit revert à une grosse rustine.

---

*Dernière mise à jour : à dater à chaque modification.*