# ROADMAP — Application de QCM en direct

> Version en cours et cases à cocher. Mise à jour à chaque fin de ticket.
> Un ticket = une case = une branche = une PR. Ne pas cocher sans preuve
> (test, capture, ou démo).

Légende : `[ ]` à faire · `[~]` en cours · `[x]` fait et vérifié · `[!]` bloqué

---

## V0 — Démo (échéance : jeudi 12 novembre 2026)

Objectif : une démo qui marche, sur le MSI personnel. Une seule séance, un seul QCM codé en dur.

- [x] Modèle de données minimal (`Quiz`, `Step`, `Question`, `Choice`, `Session`, `Participant`, `Answer`)
- [x] Admin Django : saisie d'un QCM (au moins un quiz de démo)
- [x] Page tableau : affiche l'étape courante, les 1 à 4 questions, les choix, le minuteur
- [x] Page téléphone : rejoint une session, affiche les boutons A/B/C/D, envoie une réponse
- [x] `Session.ends_at` côté serveur ; le client affiche un décompte local
- [x] Refus d'une réponse après `ends_at` (test unitaire)
- [x] Refus d'une seconde réponse à la même question (test unitaire)
- [x] **Critère de fin** : 3 téléphones rejoignent et répondent ; le prof voit les réponses arriver ; une réponse tardive est refusée.

---

## V1 — Cœur (fusionnée le 2026-11-09)

Objectif : une séance complète, avec redémarrage serveur au milieu, sans perte.

### Saisie et import
- [x] Import JSON d'un QCM (format `SPEC.md` §5)
- [x] Validation du format à l'import (erreurs claires)
- [x] Saisie complète via admin Django (images, KaTeX, code)

### Séance
- [x] Code de session + QR code généré à la création
- [x] Salon d'attente pour les élèves
- [x] 1 à 4 questions par étape, chacune avec sa couleur (`couleur_slot`)
- [x] Attribution aléatoire et persistée de la couleur + symbole par élève
- [x] Ordre des boutons mélangé par élève (`graine_mélange` persistée)
- [x] Passage automatique à l'étape suivante à `ends_at`
- [x] Contrôles prof : pause / reprise / +temps / suivant / précédent / terminer
- [x] Reconnexion : l'élève retrouve sa séance, son étape et ses réponses

### Réseau
- [x] File locale `localStorage` + `id_client` (anti-doublon)
- [x] Backoff exponentiel des tentatives
- [x] Écran « réponse validée » uniquement après accusé serveur

### Affichage
- [x] KaTeX sur le tableau
- [x] Images sur le tableau
- [x] Nombre de réponses reçues en temps réel sur le tableau

### Dette V1 — interface et usage (ticket #3, fusionnée)
- [x] Bouton « Terminer la séance » sur le tableau et le téléphone, sans page finale bloquante
- [x] Accès iPhone sur le Wi-Fi local documenté et `ALLOWED_HOSTS` configuré
- [x] Nombre de participants connectés en temps réel sur la page pré-séance
- [x] QR code affiché uniquement sur la page initiale de la session
- [x] Libellés français dans les modèles et les templates
- [x] Colonne « Groupe » dans la vue Participants (« — » en attendant la V2)

### Sécurité
- [x] Test automatique : aucun champ `enonce` / `texte` / `est_correct` dans les réponses élèves
- [x] Endpoints prof protégés par auth + propriétaire du quiz

- [x] **Critère de fin** : séance de 5 étapes avec redémarrage serveur au milieu, aucune réponse perdue (test `test_parcours_v1.py`, 87 puis 103 tests verts).

---

## V2 — Comptes, groupes et notes (en cours)

Objectif : une séance exploitable avec de vrais élèves identifiés, rattachés à un groupe, et des notes calculées et vérifiées par des tests.

### Groupes et élèves
- [ ] Modèle `Groupe` : `nom` (unique, ex. « ISIA4 »), `proprietaire` (FK User), `date_creation`. Admin Django.
- [ ] `Student.groupe` : FK nullable en migration, puis non-nullable après data-migration.
- [ ] Import CSV des participants (`nom`, `prenom`) — commande `import_participants`.
- [ ] Import JSON des participants — même commande, détection par extension.
- [ ] Génération identifiant (`code_etudiant`) + PIN (4 à 6 chiffres), `pin_hash` en base.
- [ ] Commande `liste_identifiants <groupe>` : fichier imprimable (nom, prénom, identifiant, PIN).
- [ ] Colonne « Groupe » de la vue Participants affiche le vrai nom du groupe (remplace le « — » et le TODO V2).
- [ ] `Session.groupe` : FK nullable, choix du groupe à la création de la session (`/session/creer/`).
- [ ] Page `/session/<code>/participants/` : liste du groupe (nom, prénom, identifiant, statut), passage au vert à la connexion (polling 1–2 s), compteur « X / Y connectés ».
- [ ] Endpoint `/api/etat_participants/` : renvoie nom, prénom, identifiant, `connecte`, `derniere_activite_s` — jamais le PIN ni de réponse.
- [ ] Cas `Session.groupe = NULL` : message explicite, liste des connectés (démo).

### Authentification élève
- [ ] `/api/rejoindre/` accepte `code_etudiant` + `pin` (en plus du code de session).
- [ ] Refus d'un PIN faux avec message générique (pas d'oracle sur l'identifiant).
- [ ] Un seul appareil actif par élève : `Participant.jeton_appareil` régénéré à chaque connexion ; ancien appareil → `401`.
- [ ] Vue Participants : bouton « Réinitialiser » pour libérer l'appareil d'un élève.
- [ ] Tableau prof : liste des participants connectés, identifiant affiché discrètement (jamais le PIN), heure de dernière activité.

### Notation
- [ ] Champ `Quiz.penalite_active` (booléen, défaut `True`) et `Quiz.facteur_penalite` (float, défaut `1.0`, contrainte > 0).
- [ ] Fonction pure `note_question(choix, question, *, penalite_active, facteur_penalite)` — peut retourner une valeur négative (cf. `AGENTS.md` §4).
- [ ] Fonction pure `note_seance(notes_questions)` — plancher `0` sur la somme.
- [ ] Tests `note_question` : 1 bonne / 1 cochée ; 2 bonnes / 1 cochée ; 2 bonnes / 1 bonne + 1 mauvaise **pénalité activée** ; idem **pénalité désactivée** ; 2 bonnes / 2 bonnes ; aucune réponse ; 1 bonne / 1 mauvaise → `−1.0` ; bornage à `−facteur_penalite`.
- [ ] Tests `note_seance` : somme positive ; somme nulle ; somme négative → `0.0` ; liste vide → `0.0`.
- [ ] Admin Django : case « Pénaliser les mauvaises réponses » + champ « Facteur de pénalité », avec aide.
- [ ] Vue `/resultats/<session>/` : note totale par élève (avec plancher `0`) et taux de réussite par question. Protégée par auth + propriétaire. **Note non stockée** (calcul à la volée).
- [ ] Total de séance par élève affiché avec le plancher `0`.
- [ ] Taux de réussite par question (exact, testé).

### Accessibilité
- [ ] Symboles ● ▲ ■ ◆ ★ en plus des couleurs (téléphone et tableau).
- [ ] Police Atkinson Hyperlegible sur le téléphone, fichier local (pas de CDN, pour ne pas casser hors ligne).
- [ ] Contraste élevé (WCAG AA) et zones tactiles ≥ 44×44 px.

### Sécurité et tests V2
- [ ] Le test anti-fuite reste vert après l'ajout de l'authentification élève.
- [ ] Test : un appareil qui perd la main reçoit `401` et ne peut plus répondre.
- [ ] Test : un PIN faux est refusé avec le même message qu'un identifiant inconnu.
- [ ] Test : l'import participants est transactionnel (échec → aucune ligne créée).

- [ ] **Critère de fin** (AGENTS.md §8) : calcul des notes couvert par des tests ; taux de réussite par question exact.

---

## V3 — Papier et exports

### Papier
- [ ] PDF personnalisé par élève (WeasyPrint), calqué sur les QCM INSA
- [ ] QR code par feuille (élève + QCM)
- [ ] Saisie manuelle des réponses papier dans l'admin
- [ ] Import CSV des réponses papier
- [ ] Fusion papier / appli, question par question (l'appli prime)
- [ ] Marquage `source = papier` dans les exports

### Exports et administration
- [ ] Export CSV : note par élève (sélection de la session dans l'interface)
- [ ] Export CSV : détail par question
- [ ] Export CSV : taux de réussite par question
- [ ] Export PDF : mêmes trois vues
- [ ] Statistiques élèves paramétrables (visibles après la séance si activé)
- [ ] **Import PDF de la liste des participants** — repoussé de la V2 à la V3 : l'extraction de texte et le parsing de tableaux sont coûteux et fragiles, alors que le CSV et le JSON couvrent le besoin. À rouvrir si le professeur fournit un gabarit PDF stable.

### Sets de questions (chantier séparé)
- [ ] Fusion `Quiz` / `Question` en « sets de questions » réutilisables, importables en JSON depuis l'application. Chantier structurant (refonte du modèle), à traiter dans un ticket dédié après la V3.

### Option
- [ ] Réponses tardives horodatées avant la fin, signalées « à valider » au prof

- [ ] **Critère de fin** : une feuille papier saisie + une séance appli fusionnent sans doublon.

---

## V4 — Finitions

- [ ] Statistiques de classe au tableau en fin d'étape (option)
- [ ] Mode serveur local (portable + Wi-Fi dédié), documenté
- [ ] Test de charge à 100 clients simulés (script reproductible)
- [ ] Commande de purge des noms et réponses (fin d'année)
- [ ] Guide professeur finalisé (installation, création QCM, lancement séance, exports)
- [ ] Guide élève (rejoindre, répondre, se reconnecter)
- [ ] Documentation finale : `JOURNAL.md` consolidé, ADR, prompts clés
- [ ] **Critère de fin** : test de charge à 100 sans erreur ; guide complet remis au professeur.

---

## Journal des versions

| Version | Date | Tag Git | Statut |
| :--- | :--- | :--- | :--- |
| V0 | 2026-11-09 | — | Fusionnée dans V1 |
| V1 | 2026-11-09 | `v1.0` (à créer) | Fusionnée, 103 tests verts |
| V1 + dette | 2026-11-09 | — | Fusionnée |
| V2 | — | — | En cours |