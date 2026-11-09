# ROADMAP — Application de QCM en direct

> Version en cours et cases à cocher. Mise à jour à chaque fin de ticket.
> Un ticket = une case = une branche = une PR. Ne pas cocher sans preuve
> (test, capture, ou démo).

Légende : `[ ]` à faire · `[~]` en cours · `[x]` fait et vérifié · `[!]` bloqué

---

## V0 — Démo (échéance : jeudi 12 novembre 2026)

Objectif : une démo qui marche, sur le MSI personnel. Une seule séance, un seul QCM codé en dur.

- [ ] Modèle de données minimal (`Quiz`, `Step`, `Question`, `Choice`, `Session`, `Participant`, `Answer`)
- [ ] Admin Django : saisie d'un QCM (au moins un quiz de démo)
- [ ] Page tableau : affiche l'étape courante, les 1 à 4 questions, les choix, le minuteur
- [ ] Page téléphone : rejoint une session, affiche les boutons A/B/C/D, envoie une réponse
- [ ] `Session.ends_at` côté serveur ; le client affiche un décompte local
- [ ] Refus d'une réponse après `ends_at` (test unitaire)
- [ ] Refus d'une seconde réponse à la même question (test unitaire)
- [ ] **Critère de fin** : 3 téléphones rejoignent et répondent ; le prof voit les réponses arriver ; une réponse tardive est refusée.

---

## V1 — Cœur (échéance : à confirmer)

Objectif : une séance complète, avec redémarrage serveur au milieu, sans perte.

### Saisie et import
- [ ] Import JSON d'un QCM (format `SPEC.md` §5)
- [ ] Validation du format à l'import (erreurs claires)
- [ ] Saisie complète via admin Django (images, KaTeX, code)

### Séance
- [x] Code de session + QR code généré à la création
- [x] Salon d'attente pour les élèves
- [ ] 1 à 4 questions par étape, chacune avec sa couleur (`couleur_slot`)
- [ ] Attribution aléatoire et persistée de la couleur + symbole par élève
- [ ] Ordre des boutons mélangé par élève (`graine_mélange` persistée)
- [ ] Passage automatique à l'étape suivante à `ends_at`
- [x] Contrôles prof : pause / reprise / +temps / suivant / précédent / terminer
- [ ] Reconnexion : l'élève retrouve sa séance, son étape et ses réponses

### Réseau
- [ ] File locale `localStorage` + `id_client` (anti-doublon)
- [ ] Backoff exponentiel des tentatives
- [ ] Écran « réponse validée » uniquement après accusé serveur

### Affichage
- [ ] KaTeX sur le tableau
- [ ] Images sur le tableau
- [ ] Nombre de réponses reçues en temps réel sur le tableau

### Dette V1 — interface et usage (ticket #3)
- [x] Bouton « Terminer la séance » sur le tableau et le téléphone, sans page finale bloquante
- [x] Accès iPhone sur le Wi-Fi local documenté et `ALLOWED_HOSTS` configuré
- [x] Nombre de participants connectés en temps réel sur la page pré-séance
- [x] QR code affiché uniquement sur la page initiale de la session
- [x] Libellés français dans les modèles et les templates
- [x] Colonne « Groupe » dans la vue Participants (« — » en attendant la V2)

### Sécurité
- [ ] Test automatique : aucun champ `enonce` / `texte` / `est_correct` dans les réponses élèves
- [ ] Endpoints prof protégés par auth + propriétaire du quiz

- [ ] **Critère de fin** : séance de 5 étapes avec redémarrage serveur au milieu, aucune réponse perdue.

---

## V2 — Comptes et notes

### Élèves
- [ ] Import CSV de la liste de classe (nom, prénom)
- [ ] Import JSON de la liste de classe (nom, prénom)
- [ ] Chaques participants doivent appartenir à un groupe
- [ ] Génération identifiant + PIN, hash du PIN
- [ ] Liste imprimable pour la distribution
- [ ] Un seul appareil actif par élève (nouvelle connexion remplace l'ancienne)
- [ ] Un affichage sur le tableau professeur de la liste de participants / Leur identifiant de connexion associé
- [ ] Le prof voit qui est connecté et peut réinitialiser l'appareil d'un élève

### Notation
- [ ] Champ `Quiz.penalite_active` (booléen, défaut `True`) et `Quiz.facteur_penalite` (float, défaut `1.0`)
- [ ] Fonction pure `note_question(choix, question, *, penalite_active, facteur_penalite)` — peut retourner une valeur négative
- [ ] Fonction pure `note_seance(notes_questions)` — plancher `0` sur la somme
- [ ] Tests `note_question` : 1 bonne / 1 cochée ; 2 bonnes / 1 cochée ; 2 bonnes / 1 bonne + 1 mauvaise **pénalité activée** ; idem **pénalité désactivée** ; 2 bonnes / 2 bonnes ; aucune réponse ; 1 bonne / 1 mauvaise → `−1.0` ; bornage à `−facteur_penalite`
- [ ] Tests `note_seance` : somme positive ; somme nulle ; somme négative → `0.0` ; liste vide → `0.0`
- [ ] Admin Django : case « Pénaliser les mauvaises réponses » + champ « Facteur de pénalité »
- [ ] Total de séance par élève affiché avec le plancher `0`
- [ ] Taux de réussite par question (exact, testé)

### Accessibilité
- [ ] Symboles ● ▲ ■ ◆ ★ en plus des couleurs
- [ ] Police Atkinson Hyperlegible sur le téléphone
- [ ] Contraste élevé, grandes zones tactiles

- [ ] **Critère de fin** : calcul des notes couvert par des tests ; taux de réussite par question exact.

---

## V3 — Papier et exports

### Papier
- [ ] PDF personnalisé par élève (WeasyPrint), calqué sur les QCM INSA
- [ ] QR code par feuille (élève + QCM)
- [ ] Saisie manuelle des réponses papier dans l'admin
- [ ] Import CSV des réponses papier
- [ ] Fusion papier / appli, question par question (l'appli prime)
- [ ] Marquage `source = papier` dans les exports

### Exports
- [ ] Export CSV : note par élève
- [ ] Export CSV : détail par question
- [ ] Export CSV : taux de réussite par question
- [ ] Export PDF : mêmes trois vues
- [ ] Statistiques élèves paramétrables (visibles après la séance si activé)

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

## Points ouverts (bloquants pour la version concernée)

| Point | Version concernée | Statut |
| :--- | :--- | :--- |
| Barème partiel exact et note sans réponse | V2 | À trancher avec le prof |
| Durée de conservation des données | V4 | À trancher avec le DPO INSA |
| Format JSON d'import définitif | V1 | À figer avant l'import |
| Tolérance de latence sur les réponses proches de la fin | V1 | À trancher |
| Date du rendu final et format du guide | V4 | À confirmer |
| Nombre de couleurs 4 et jeu de symboles | V1 | À figer |
| Facteur de pénalité par défaut | V2 | À trancher avec le prof |
| Pénalité par quiz ou par séance ? | V2 | À trancher |
---

## Journal des versions

| Version | Date | Tag Git | Statut |
| :--- |