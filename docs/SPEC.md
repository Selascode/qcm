# SPEC — Application de QCM en direct (PAO INSA Rouen)

> Source de vérité fonctionnelle. En cas de conflit avec `AGENTS.md`, `AGENTS.md` prime
> sur les règles de sécurité et de stack ; ce document prime sur les détails fonctionnels.

Version : 2.0 — alignée sur la V2 (comptes, groupes, notes, rotation par blocs).

---

## 1. Contexte et objectifs

Application web de QCM en direct, utilisée en contrôle continu. Le professeur projette
les questions au tableau ; les élèves répondent depuis leur téléphone **sans jamais
voir l'énoncé**. Développée en vibe coding avec des agents, dans le cadre du PAO.

**Objectif pédagogique** : évaluer les élèves en direct, avec des notes exploitables.

---

## 2. Utilisateurs et périmètre

| Rôle | Ce qu'il fait |
| :--- | :--- |
| Professeur | Compte distinct protégé. Configure les QCM, importe les groupes, lance la séance, pilote, consulte les résultats. |
| Élève | Rejoint par QR code ou code de session, s'identifie (identifiant) , répond sur son téléphone. |

**Sécurité de l'accueil** : La page d'accueil (`/`) est publique et ne permet que de
rejoindre une séance ou de s'authentifier (« Espace professeur »). La création de séance
et la gestion des QCM sont strictement réservées aux professeurs authentifiés.

---

## 3. Déroulement d'une séance et répartition

Une séance est une suite d'**étapes**. Chaque étape affiche de 1 à 4 questions en même
temps et possède son propre minuteur.

**Contrôles du professeur** : pause, reprise, ajout de temps, étape suivante, étape
précédente. Le minuteur seul fait avancer la séance par défaut.

**Répartition automatique (Rotation par blocs) :**
Le professeur n'a pas à découper manuellement son QCM. L'application génère
automatiquement les étapes pour que **chaque élève réponde à toutes les questions**.
- Les questions sont regroupées en "paquets" (taille max = 4).
- Un paquet de \(T\) questions génère \(T\) étapes identiques (affichant les \(T\) questions).
- À chaque étape, la couleur de l'élève tourne, l'obligeant à répondre à une question
  différente du paquet. En \(T\) étapes, il a répondu à toutes les questions du paquet.
- *Exemple (10 questions, max 4)* : 10 étapes au total. Les 4 premières affichent Q1-Q4,
  les 4 suivantes Q5-Q8, les 2 dernières Q9-Q10.

Paquet 1 (Q1, Q2, Q3, Q4) - 4 étapes :
    Étape 1 : Alice a la couleur 1 (répond à Q1). Bob a la couleur 2 (répond à Q2).
    Étape 2 : Alice a la couleur 2 (répond à Q2). Bob a la couleur 3 (répond à Q3).
    Étape 3 : Alice a la couleur 3 (répond à Q3). Bob a la couleur 4 (répond à Q4).
    Étape 4 : Alice a la couleur 4 (répond à Q4). Bob a la couleur 1 (répond à Q1).
    (Fin du paquet 1 : Alice a répondu à Q1, Q2, Q3, Q4. Bob a répondu à Q2, Q3, Q4, Q1.)

Paquet 2 (Q5, Q6, Q7, Q8) - 4 étapes :
    Étape 5 : Alice (couleur 1) répond à Q5. Bob (couleur 2) répond à Q6.
    Étape 6 : Alice (couleur 2) répond à Q6. Bob (couleur 3) répond à Q7.
    Étape 7 : Alice (couleur 3) répond à Q7. Bob (couleur 4) répond à Q8.
    Étape 8 : Alice (couleur 4) répond à Q8. Bob (couleur 1) répond à Q5.
    (Fin du paquet 2 : Alice et Bob ont répondu à Q5, Q6, Q7, Q8.)

Paquet 3 (Q9, Q10) - 2 étapes :
    Étape 9 : Alice (couleur 1) répond à Q9. Bob (couleur 2) répond à Q10.
    Étape 10 : Alice (couleur 2) répond à Q10. Bob (couleur 1) répond à Q9.
    (Fin du paquet 3 : Alice et Bob ont répondu à Q9 et Q10.)

**Règles côté élève :**
- Une réponse est **définitive** (pas de modification).
- Une réponse reçue après `ends_at` n'est **jamais** prise en compte.
- L'élève qui se déconnecte retrouve son état (séance, étape, réponses).

---

## 4. Affichage tableau et téléphone

**Tableau (vidéoprojecteur) :**
- **Mode Présentation** : une vue dédiée (nouvel onglet/plein écran) affichant UNIQUEMENT
  les questions, les choix, le timer géant et les compteurs. Aucun bouton de contrôle
  (pause, suivant) ne doit y apparaître. Les contrôles restent sur la vue prof principale.
- 1 à 4 questions côte à côte, couleurs, réponses (A, B, C, D…), KaTeX et images.

**Téléphone (mobile first) :**
- Boutons A, B, C, D… avec la couleur assignée, temps restant.
- **Aucun énoncé** dans la page ni les échanges réseau.
- Écran « réponse validée » uniquement après accusé serveur.

**Accessibilité** : Symboles (● ▲ ■ ◆ ★) en plus des couleurs, police Atkinson
Hyperlegible, contraste WCAG AA, zones tactiles ≥ 44x44px.

---

## 5. Questions et notation

**Contenu d'une question** : énoncé, 2 à 6 choix, type (unique/multiple).
**Barème (fonctions pures, configurables)** : Voir `AGENTS.md` §4.
- La note par question peut être négative (jusqu'à `-facteur_penalite`).
- La note finale de la séance est plafonnée à `0` (`max(0, somme)`).

---

## 6. Identifiants et gestion des groupes

- Modèle `Groupe` (nom, propriétaire). L'élève appartient à un groupe.
- **Import des élèves** : Accessible **depuis l'interface professeur** (bouton « Importer »
  dans la vue Groupe). Formulaire d'upload CSV/JSON. La commande CLI reste disponible.
- **Identifiants sans PIN** : L'application génère uniquement un identifiant lisible
  (ex: `MARIE-DUP33`). Il n'y a pas de code PIN à distribuer. L'élève se connecte
  simplement avec son identifiant, qu'il lit sur l'écran de pré-séance.
- **Un seul appareil actif** : Si un élève se connecte, l'appareil devient le sien.
  Une nouvelle connexion avec le même identifiant remplace l'ancienne (ou est bloquée
  selon le choix du prof). Le prof peut réinitialiser l'appareil d'un élève depuis
  la vue Participants.
- **Écran pré-séance (Contrôle visuel)** : Page dédiée affichant la liste complète du
  groupe (Nom, Prénom, Identifiant). Les élèves passent au vert en direct à la connexion
  (polling). Le professeur peut ainsi vérifier qui est absent ou connecté.
- En plus de l'identifiant de connexion généré (code_etudiant), un élève peut avoir un identifiant_insa optionnel (fourni par l'école). Ce champ est utilisé pour les exports de notes vers les outils de l'INSA, mais n'est pas utilisé pour la connexion à l'application.
---

## 7. Architecture technique (résumé — détail dans `ARCHITECTURE.md`)

| Sujet | Choix retenu |
| :--- | :--- |
| Temps réel | Polling `/etat/` toutes les 1-2 s (pas de WebSockets). |
| Base | SQLite (WAL) en dev, PostgreSQL en prod. ORM uniquement. |
| Front | Django + HTMX + JS simple. KaTeX. |

---

## 8. Réseau et mode dégradé

- File locale `localStorage` + `id_client` pour anti-doublon.
- Mode papier (V3) : PDF généré, fusion appli/papier (l'appli prime).

---

## 9. Sécurité, confidentialité et données personnelles

- **Aucun énoncé, texte de choix ou champ `est_correct` ne quitte le serveur vers les téléphones.**
- Test automatique vérifiant l'absence de ces champs dans les endpoints élèves.
- La note est calculée côté serveur uniquement.
- Données stockées : prénom, nom, identifiant, réponses.

---

## 10. Résultats et exports

- Notes par élève, détail par question, taux de réussite.
- Exports CSV/PDF (V3).
