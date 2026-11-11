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
## Dette V2 (Corrections urgentes)
- [ ] **Accueil** : retirer le bouton « Créer une séance » pour les anonymes.
- [ ] **Admin** : renommer `Student` -> "Élève (Base)" et `Participant` -> "Élève (Session)" pour supprimer les doublons.
- [ ] **Bug Import** : corriger la commande `import_participants` (`nom__iexact`) pour qu'elle trouve le groupe "ISIA4".
- [ ] **Tests Import** : ajouter des tests d'intégration pour l'import (CSV/JSON) avec un vrai groupe.
---

## V2 — Comptes élèves, Import et Corrections (En cours / À merger)

- [x] Modèle `Groupe` et rattachement de `Session` et `Student`.
- [x] **Sécurité Accueil** : retirer « Créer une séance » pour les anonymes.
- [x] **Admin** : renommer `Student` -> "Élève (Base)" et `Participant` -> "Élève (Session)".
- [x] **Sans PIN** : suppression de `pin_hash`, génération d'identifiant lisible (`MARIE-DUP`).
- [x] **Import Web** : page `/groupe/<id>/importer-eleves/` avec upload CSV/JSON.
- [x] **Écran pré-séance** : liste des élèves avec statut vert en direct.
- [x] **Mode Présentation** : vue plein écran sans boutons de contrôle.
- [x] **Algorithme de répartition** : génération des étapes par paquets de 4.

---

## Dette V2 (Corrections urgentes avant V3)

- [ ] **Admin Groupe** : ajouter un `InlineModelAdmin` pour voir et modifier les élèves directement depuis la page du Groupe.
- [ ] **Couleurs Round-Robin** : remplacer le hasard par une attribution cyclique (1, 2, 3, 4, 1, 2...) pour éviter que 2 élèves aient la même couleur (et donc la même question).
- [ ] **Tests Round-Robin** : vérifier que 4 connexions donnent 4 couleurs distinctes.

---

## V3 — Banque de questions (Sets) et Exports

### Banque de questions (`QuestionSet`)
- [ ] Créer le modèle `QuestionSet` (nom, propriétaire).
- [ ] Data migration pour migrer les questions existantes dans un set par défaut.
- [ ] Modifier le modèle `Quiz` (ManyToMany vers `Question` au lieu de `Step` direct).
- [ ] Interface : menu "Questions" qui liste les Sets, puis les questions du set.
- [ ] Interface : import de questions (JSON/CSV) directement depuis l'admin (comme pour les élèves).
- [ ] Adapter `generer_etapes()` pour piocher dans les questions du Quiz sélectionné.

### Papier et Exports
- [ ] PDF personnalisé par élève (WeasyPrint).
- [ ] Saisie manuelle des réponses papier dans l'admin.
- [ ] Fusion papier / appli (l'appli prime).
- [ ] Export CSV : notes par élève, détail par question, taux de réussite.

---

## V4 — Finitions

- [ ] Statistiques de classe au tableau en fin d'étape (option).
- [ ] Mode serveur local (portable + Wi-Fi dédié).
- [ ] Test de charge à 100 clients simulés.
- [ ] Guide professeur finalisé.

---

## Journal des versions

| Version | Date | Tag Git | Statut |
| :--- | :--- | :--- | :--- |
| V0 / V1 | 2026-11-09 | `v1.0` | Fusionnée |
| V2 | 2026-11-11 | `v2.0` (à venir) | PR en cours de revue (189 tests) |
| V3 | — | — | À planifier (Sets, Round-Robin, Admin) |