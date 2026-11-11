# ARCHITECTURE — Application de QCM en direct

> Document technique de référence. La spec fonctionnelle est dans `SPEC.md`.
> Les règles impératives sont dans `AGENTS.md`.

Version : 2.0 — alignée sur la V2/V3.

---

## 1. Vue d'ensemble

- **Un seul serveur Django**, pas de Channels, pas de SSE.
- **Le serveur est la seule référence temporelle** (`ends_at` en base).
- **Les énoncés ne sortent jamais** vers les endpoints élèves.
- **Polling** (1-2 s) pour le temps réel.

---

## 2. Modèle de données

```text
User (professeur, Django auth)
│
├── Groupe          : nom (unique), proprietaire (FK User)
│   └── Student     : nom, prenom, groupe (FK), code_etudiant (unique, lisible)
│
├── QuestionSet     : nom, proprietaire (FK User)  <-- NOUVEAU (V3)
│   └── Question    : set (FK), uid (unique par set), enonce, image?, type
│       └── Choice  : question, lettre, texte, est_correct, position
│
├── Quiz            : titre, proprietaire (FK User)
│   ├── questions   : ManyToMany vers Question (sélection pour la séance) <-- NOUVEAU (V3)
│   └── Session     : quiz, groupe (FK), code_session, statut, etape_courante, ends_at
│       └── Participant : session, student, couleur_assignee (Round-Robin), graine_melange, jeton_appareil
│           └── Answer  : session, participant, question, choix_selectionnes, recu_a, source, id_client
│                         contrainte unique (participant, question)
```
### Détails importants

- **Banque de questions** : Le `QuestionSet` permet de réutiliser les questions. Le `Quiz` ne crée plus les questions, il les sélectionne.
- **Identifiants sans PIN** : `Student.code_etudiant` est unique et lisible. Il n'y a pas de mot de passe.
- **Couleurs Round-Robin** : À la connexion, la couleur est `(nombre_de_participants_déjà_connectés % 4) + 1`. Le 1er a 1, le 2ème a 2, etc. Cela garantit que sur 4 élèves, aucun n'a la même couleur.
- **Algorithme de répartition (`qcm/services/repartition.py`)** :
  - Prend la liste des questions sélectionnées pour le Quiz.
  - Les regroupe en paquets de 4 maximum.
  - Un paquet de \(T\) questions génère \(T\) étapes virtuelles (le paquet est réaffiché \(T\) fois).
  - La couleur de l'élève tourne à chaque étape (`(couleur_initiale + étape - 1) % T`), l'obligeant à répondre à une question différente à chaque passage.
- **Timer** : `Session.ends_at` est la seule référence. Pause = `ends_at = NULL` + `reste_en_pause`.

---

## 3. Endpoints

### Côté élève
| Méthode | URL | Rôle |
| :--- | :--- | :--- |
| `POST` | `/api/rejoindre/` | Rejoindre avec `code_session` + `code_etudiant` (sans PIN). |
| `GET` | `/api/etat/` | Renvoie `{etape, couleur, nb_choix, temps_restant_s, statut}`. |
| `POST` | `/api/repondre/` | Envoyer une réponse (refus si tardif ou doublon). |

### Côté professeur
| Méthode | URL | Rôle |
| :--- | :--- | :--- |
| `GET` | `/tableau/<code>/` | Tableau avec contrôles. |
| `GET` | `/tableau/<code>/presentation/` | **Nouveau** : Vue propre (timer géant, questions, pas de contrôles). |
| `GET/POST` | `/groupe/<id>/importer-eleves/` | **Nouveau** : Interface web d'import. |
| `GET` | `/api/etat_participants/` | **Nouveau** : Liste des élèves du groupe et statut connecté (vert/gris). |

---

## 4. Séquence de rotation (Exemple 5 questions, max 4)

L'algorithme `generer_etapes()` crée 2 paquets : [Q1, Q2, Q3, Q4] et [Q5].
- Le paquet 1 génère 4 étapes (affichant Q1-Q4).
- Le paquet 2 génère 1 étape (affichant Q5).
- Total : 5 étapes.
- À chaque étape, la couleur de l'élève tourne de +1, l'obligeant à changer de question.

---

## 5. Front

- **Tableau** : Template Django + HTMX + KaTeX.
- **Téléphone** : Template minimal + JS vanilla (`localStorage` pour la file d'attente).
- **Admin** : `InlineModelAdmin` pour gérer les élèves directement depuis le Groupe (V3).

---

## 6. Notation

Fonctions pures `note_question` et `note_seance` dans `notation.py`. La note n'est jamais stockée en base.

---

## 7. Décisions liées

- ADR 0001 : Format d'import JSON.
- ADR 0002 : Tolérance de latence 0s.
- ADR 0003 : Couleurs et symboles.
- ADR 0004 : Répartition des élèves.
- ADR 0008 : Suppression du PIN (authentification par identifiant seul).