
# ARCHITECTURE — Application de QCM en direct

> Document technique de référence. La spec fonctionnelle est dans `SPEC.md`.
> Les règles impératives sont dans `AGENTS.md`.

Version : 1.0 — alignée sur la V0/V1. À mettre à jour à chaque changement structurant
(et à accompagner d'une ADR dans `docs/decisions/`).

---

## 1. Vue d'ensemble

```
┌──────────────────┐        polling /etat/ (1–2 s)        ┌──────────────────┐
│  Téléphone élève │ ──────────────────────────────────▶ │                  │
│  (HTML + JS)     │ ◀────────────────────────────────── │   Django (WSGI)  │
└──────────────────┘        JSON minimal (sans énoncé)   │                  │
                                                          │   ORM uniquement │
┌──────────────────┐        polling /etat_prof/          │                  │
│  Tableau (vidéo) │ ──────────────────────────────────▶ │   SQLite (WAL)   │
│  + interface prof│ ◀────────────────────────────────── │   ou PostgreSQL  │
└──────────────────┘        HTML / JSON complet          └──────────────────┘
```

Principes :

- **Un seul serveur Django**, pas de Channels, pas de SSE, pas de worker séparé.
- **Le serveur est la seule référence temporelle** (`ends_at` en base).
- **Les énoncés ne sortent jamais** vers les endpoints élèves.
- Le polling est volontairement simple : il reprend naturellement après une coupure,
  il tient dans Django seul, et il suffit pour 100 clients (à vérifier en V4 par un
  test de charge ; si insuffisant, on ouvre un ticket dédié avant de changer de techno).

---

## 2. Modèle de données

Le schéma ci-dessous est la référence. Les invariants sont rappelés dans `AGENTS.md` §3.

```text
User (professeur, Django auth)
│
├── Quiz            : titre, propriétaire (FK User)
│   ├── Step        : quiz, numéro, durée_s
│   │   └── Question: step, uid (unique PAR quiz), énoncé, image?, type
│   │                (unique/multiple), afficher_indice_multiple, ordre,
│   │                couleur_slot (1..4)
│   │       └── Choice : question, lettre, texte, est_correct, position
│   │
│   └── Session     : quiz, code_session, statut (attente/en_cours/pause/fini),
│                     étape_courante, ends_at, reste_en_pause
│           └── Participant` (`verbose_name = "Élève (Session)"`) : session, student,
  couleur_assignée, graine_mélange, jeton_appareil.
│                   └── Answer : session, participant, question, choix_sélectionnés,
│                                 reçu_à, source (app/papier), id_client
│                                 contrainte unique (participant, question)
│
└── `Student` (`verbose_name = "Élève (Base)"`) : nom, prénom, groupe (FK),
  code_etudiant (unique, lisible)

```

### Détails importants

- **`Step.durée_s`** porte la durée, pas `Question`. Une étape regroupe 1 à 4 questions.
- **`Question.uid`** est unique **par quiz**. Il est repris sur le tableau (discrètement)
  et sur le papier, pour la réconciliation.
- **`Question.couleur_slot`** ∈ {1..4}. C'est l'indice de couleur de la question, pas
  la couleur de l'élève. L'élève se voit attribuer une couleur (et un symbole) via
  `Participant.couleur_assignée`, tirée au hasard, persistée.
- **Répartition élève → question** : les questions de l'étape sont ordonnées, et
  l'élève reçoit l'indice `(couleur_assignée - 1) % nombre_de_questions`. Avec 4
  questions, sa couleur tombe sur sa colonne ; avec 1 à 3, la répartition est
  repliée pour que chaque élève ait une question (ADR 0004).
- **`Question.quiz`** (FK dénormalisée, non éditable) double la hiérarchie
  `Step → Quiz` uniquement pour garantir l'unicité `(quiz, uid)` en base.
- **`Participant.graine_mélange`** permet de reconstituer l'ordre des boutons d'un élève
  après redémarrage (permutation déterministe à partir de la graine).
- **`Answer.choix_sélectionnés`** stocke les lettres cochées (ex. `["A","C"]`), pas des
  FK. Cela rend la lecture et l'export triviaux, et évite une table de jointure.
- **`Answer.source`** ∈ {`app`, `papier`}. Prépare la V3.
- **`Answer.id_client`** : UUID généré côté téléphone, sert d'anti-doublon pour la file
  locale. Contrainte unique globale (pas seulement par participant).
- **Contrainte unique `(participant, question)`** : une seule réponse définitive par
  question et par élève. Ne jamais la retirer.
- **`Session.ends_at`** est la seule référence temporelle. Pause : on stocke
  `reste_en_pause` (secondes restantes) et on met `ends_at = NULL`. Reprise : on
  recalcule `ends_at = now() + reste_en_pause`. Ajout de temps : `ends_at += delta`.

### Index recommandés

- `Answer (participant, question)` — déjà couvert par la contrainte unique.
- `Answer (session)` — pour les exports et les comptages en direct.
- `Participant (session, student)` — unique.
- `Session (code_session)` — unique, indexé.
- `Question (step, ordre)` — pour l'affichage tableau.

---

## 3. Endpoints (V0/V1)

Tous les endpoints sont en JSON, sauf la page tableau (HTML) et l'admin.

### Côté élève (aucune fuite d'énoncé)

| Méthode | URL | Rôle | Réponse |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/rejoindre/` | Rejoindre une session avec code + identifiant | `{ok, session_id, participant_id, jeton}` |
| `GET` | `/api/etat/` | État courant pour l'élève (polling 1–2 s) | `{etape, couleur, nb_choix, temps_restant_s, statut, deja_repondu}` |
| `POST` | `/api/repondre/` | Envoyer une réponse | `{ok, recu: true, id_client}` ou `{ok: false, raison}` |

**Règles strictes sur `/api/etat/` :**

- Ne renvoie **jamais** `enonce`, `texte` (des choix), `est_correct`, ni le nombre de
  bonnes réponses.
- Renvoie la **couleur** et le **symbole** de la question à laquelle l'élève doit répondre,
  le nombre de choix, l'ordre mélangé des lettres (pour générer les boutons), l'`uid`
  de la question (repère non secret) et le temps restant calculé à partir de
  `ends_at` côté serveur.
- Si l'élève a déjà répondu à la question courante, renvoie `deja_repondu: true` et
  l'écran « réponse validée » peut s'afficher.

**Règles sur `/api/repondre/` :**

- Refuse si `now() > ends_at` (tolérance nulle : l'heure du serveur fait foi, ADR 0002).
- Refuse si une réponse existe déjà pour `(participant, question)`.
- Refuse si `id_client` a déjà été vu (anti-doublon de la file locale).
- Ne renvoie **jamais** la bonne réponse.

### Côté professeur / tableau

| Méthode | URL | Rôle |
| :--- | :--- | :--- |
| `GET` | `/tableau/<code>/` | Page HTML du tableau (protégée par auth prof) |
| `GET` | `/api/etat_prof/` | État complet pour le tableau (énoncés, choix, compteurs, timer) |
| `POST` | `/api/piloter/` | Pause / reprise / +temps / suivant / précédent |
| `GET` | `/api/resultats/<session>/` | Notes et détail (protégé) |
| `GET` | `/export/<session>/csv/` | Export CSV (protégé) |
| `GET` | `/export/<session>/pdf/` | Export PDF (protégé, V3) |

Tous les endpoints prof sont protégés par `login_required` + vérification que l'utilisateur
est bien le propriétaire du quiz.

---

## 4. Séquence : déroulement d'une étape

```
Professeur            Serveur                     Téléphone élève
    │                    │                              │
    │ POST /piloter/     │                              │
    │ (suivant)          │                              │
    ├───────────────────▶│                              │
    │                    │ met à jour Session.étape_courante
    │                    │ et Session.ends_at = now()+durée
    │                    │                              │
    │                    │◀──── GET /api/etat/ ─────────┤ (polling 1–2 s)
    │                    │───── {etape, couleur, ──────▶│
    │                    │       nb_choix, temps_restant}│
    │                    │                              │
    │                    │◀──── POST /api/repondre/ ────┤ (l'élève clique)
    │                    │  vérifie ends_at, doublon    │
    │                    │───── {ok, recu: true} ──────▶│
    │                    │                              │ affiche « validé »
    │                    │                              │
    │ (à la fin du temps)│                              │
    │                    │ passe automatiquement à      │
    │                    │ l'étape suivante (cron léger │
    │                    │ ou calcul à la volée sur     │
    │                    │ chaque requête /etat/)       │
```

**Passage automatique à l'étape suivante** : pas de cron. À chaque requête `/etat/`
(élève) ou `/etat_prof/`, le serveur vérifie si `now() > ends_at`. Si oui, il avance
`étape_courante` et recalcule `ends_at`. C'est idempotent et suffisant pour 100 clients.

---

## 5. Front

- **Tableau** : template Django rendu côté serveur + HTMX pour rafraîchir les compteurs
  (ou polling JS simple). KaTeX chargé sur cette page uniquement.
- **Téléphone** : template minimal, mobile first, sans KaTeX, sans énoncé. JS vanilla
  pour le polling et la file locale (`localStorage`).
- **Admin Django** : saisie des questions dès la V1. Pas d'interface prof custom avant V2.

---

## 6. File locale de réponses (V1)

Côté téléphone :

1. Au clic sur un bouton, générer un `id_client` (UUID v4).
2. Écrire `{id_client, question_uid, choix, timestamp_local}` dans `localStorage`.
3. Tenter `POST /api/repondre/`.
4. Si échec réseau : marquer « en attente », réessayer avec backoff exponentiel
   (1 s, 2 s, 4 s, 8 s, plafonné à 30 s).
5. Au retour du réseau, vider la file dans l'ordre.
6. Le serveur ignore les doublons via `id_client`.

L'écran « réponse validée » ne s'affiche **qu'après** l'accusé de réception du serveur.

---

## 7. Notation (fonctions pures, configurables)

`notation.py` expose deux fonctions pures, sans accès à la base :

```python
def note_question(
    choix_selectionnes: list[str],
    question: Question,
    *,
    penalite_active: bool = True,
    facteur_penalite: float = 1.0,
) -> float:
    """Note d'une question, bornée entre -facteur_penalite et 1.

    - choix_selectionnes : lettres cochées (ex. ["A", "C"])
    - question : instance avec ses Choice (bonnes réponses connues)
    - penalite_active : si False, les mauvaises réponses ne retirent rien
    - facteur_penalite : multiplicateur appliqué aux mauvaises réponses

    Formule interne :
        brut = (bonnes_cochées - facteur_penalite * mauvaises_cochées) / nb_bonnes
    Retour : max(-facteur_penalite, min(1.0, brut))
    """

def note_seance(notes_questions: list[float]) -> float:
    """Note finale d'une séance : max(0, somme(notes_questions))."""

---

## 8. Décisions liées

Les choix structurants sont documentés dans `docs/decisions/`.

ADR de la V1 (créés avec ce ticket) :

- `0001-format-import-json-v1.md`
- `0002-tolerance-latence-zero.md`
- `0003-couleurs-et-symboles-v1.md`
- `0004-repartition-eleves-couleurs.md`

D'autres ADR restent à créer au fil de l'eau, sans numéro réservé : polling
plutôt que WebSockets, SQLite WAL puis PostgreSQL, notation en fonction pure,
uid de question unique par quiz. Chaque ADR suit le format : contexte,
options, décision, conséquences.

