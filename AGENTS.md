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

1. **Aucun énoncé, texte de choix ou champ `est_correct` ne doit jamais partir vers un téléphone élève.**
   - Les endpoints élèves (`/etat/`, `/repondre/`, etc.) ne renvoient que : couleur de la question, nombre de choix, temps restant, accusé de réception, statut de la réponse.
   - Tout nouveau champ ajouté à une réponse JSON destinée à l'élève doit être justifié dans le plan.
2. **La note est calculée uniquement côté serveur.** Jamais dans le navigateur, jamais renvoyée à l'élève avant la fin de la séance (sauf si le prof a activé les stats élèves).
3. **L'heure de référence est toujours celle du serveur.** `ends_at` est stocké en base. Le client ne fait qu'afficher un décompte local à partir de l'heure serveur. Aucune décision d'acceptation/refus d'une réponse ne se prend côté client.
4. **Une réponse reçue après `ends_at` est refusée.** Une seconde réponse à la même question est refusée (contrainte unique `(participant, question)`).
5. **Chaque ticket qui touche un endpoint élève doit être accompagné d'un test** qui parcourt le JSON de réponse et échoue si `enonce`, `texte` (des choix), ou `est_correct` apparaît.

---

## 2. Stack figée

- **Backend** : Django + Python, **ORM uniquement** (pas de SQL brut).
- **Front** : templates Django + **HTMX** + JavaScript simple. Pas de framework JS.
- **Formules** : KaTeX (côté tableau uniquement).
- **Base** : SQLite en mode WAL pour le dev/démo ; PostgreSQL pour l'école. ORM compatible avec les deux.
- **Temps réel** : **polling** d'un endpoint léger `/etat/` toutes les 1 à 2 s avec délai aléatoire. **Pas de SSE, pas de Channels, pas de WebSockets** sauf si un test de charge prouve que le polling ne suffit pas.
- **Tests** : `pytest` + `pytest-django`.
- **Style** : `ruff` (config par défaut).

Toute nouvelle dépendance doit être justifiée, ajoutée à `requirements.txt` avec version épinglée, et signalée dans la PR.

---

## 3. Modèle de données — invariants

- **Banque de questions (`QuestionSet`)** : Une `Question` appartient à un `QuestionSet` (réutilisable). Un `Quiz` sélectionne des `Questions` dans la banque. L'algorithme de répartition pioche dans cette sélection.
- **Identifiants sans PIN** : Le modèle `Student` n'a pas de `pin_hash`. Il a un `code_etudiant` unique (ex: `MARIE-DUP00`). L'authentification se fait uniquement par ce code.
- **Couleurs déterministes** : `Participant.couleur_assignée` n'est **pas** aléatoire. Elle est assignée de manière cyclique (Round-Robin) à la connexion (le 1er a la couleur 1, le 2ème la 2, etc.) pour minimiser les doublons.
- `Answer` a une **contrainte unique `(participant, question)`**.
- `Answer` porte `source` (`app` / `papier`) et `id_client` (anti-doublon).
- `Session.ends_at` est la **seule** référence temporelle.
- `Participant.graine_mélange` est **persisté** pour l'ordre des boutons.
- `Question.uid` est unique **par quiz** (ou par `QuestionSet` en V3), pas globalement.
- La durée est portée par l'étape générée, pas par `Question`.

---

## 4. Barème — fonction pure, configurable, testée

Le barème ne doit **jamais** être stocké en base ni dupliqué dans une vue.
Il est calculé par des fonctions pures (`notation.py::note_question` et `note_seance`) qui reçoivent leur configuration en paramètre.

### Règles métier (non négociables)
1. **Pénalité optionnelle** : activable/désactivable par le professeur (0 point retiré si désactivée).
2. **Note par question négative possible** : bornée entre `−facteur_penalite` et `1`.
3. **Note finale plafonnée à 0** : `max(0, somme_des_notes)`.
4. **Pondération partielle** : `(bonnes cochées − facteur_penalite × mauvaises cochées) / nombre de bonnes réponses`.
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

```
---

## 5. Processus par ticket

1. **Lire** le ticket et la documentation.
2. **Écrire un plan court** dans l'Issue.
3. **Créer la branche** `agent/<nom-du-ticket>`.
4. **Écrire ou compléter les tests d'abord** (notation, timer, refus tardif, absence d'énoncé).
5. **Implémenter** en petits diffs relisibles.
6. **Lancer** `pytest` et `ruff`. Ne pas pousser si ça échoue.
7. **Ouvrir la PR** avec : résumé, critères d'acceptation, mention des dépendances.
8. **Ne jamais merger** : la fusion est manuelle (`Selascode`).

---

## 6. Documentation obligatoire

- **`JOURNAL.md`** : une entrée par session (objectif, prompt, résultat, décision).
- **`docs/decisions/NNNN-titre.md`** : pour tout choix structurant (ADR).
- **`prompts/`** : un fichier par prompt clé (succès et échecs).
- Une fonctionnalité terminée = un tag Git.

---

## 7. Ce que l'agent ne doit pas faire

- Créer une fonctionnalité non demandée dans le ticket.
- Réécrire un fichier entier pour corriger trois lignes.
- Changer le barème, le schéma de `Answer`, ou la politique de polling sans ticket dédié.
- Ajouter un `print` de debug.
- Modifier `AGENTS.md`, `docs/SPEC.md` ou `docs/ROADMAP.md` sans instruction explicite.
- Toucher à la configuration `dsh-superagent`.
- Utiliser `git push --force` sur `main` ou une branche en PR.

---

## 8. Critères de « terminé » par version

| Version | Critère mesurable |
| :--- | :--- |
| **V0** | 3 téléphones rejoignent, répondent, réponse tardive refusée. |
| **V1** | Séance de 5 étapes avec redémarrage serveur, aucune réponse perdue. |
| **V2** | Notes testées ; taux de réussite exact ; pas de PIN ; import web. |
| **V3** | Banque de questions (sets) fonctionnelle ; rotation des couleurs Round-Robin sans doublon. |
| **V4** | Test de charge à 100 clients sans erreur ; guide remis. |

---

## 9. En cas de blocage

- Reformuler le problème dans l'Issue.
- Si une correction s'enlise (2 échecs), **revenir en arrière** (`git reset`) et proposer une autre approche.
- Ne pas empiler les correctifs sur un code douteux.

---

*Dernière mise à jour : 2026-11-11 (Banque de questions, sans PIN, couleurs Round-Robin).*