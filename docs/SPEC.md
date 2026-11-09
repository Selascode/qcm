
# SPEC — Application de QCM en direct (PAO INSA Rouen)

> Source de vérité fonctionnelle. En cas de conflit avec `AGENTS.md`, `AGENTS.md` prime
> sur les règles de sécurité et de stack ; ce document prime sur les détails fonctionnels.
> Toute évolution de la spec passe par une PR dédiée et une entrée dans `JOURNAL.md`.

Version : 1.0 — figée pour la V0/V1. 

---

## 1. Contexte et objectifs

Application web de QCM en direct, utilisée en contrôle continu pendant les CM.
Le professeur projette les questions au tableau ; les élèves répondent depuis leur
téléphone **sans jamais voir l'énoncé**. Développée en vibe coding avec des agents,
dans le cadre du PAO de l'INSA Rouen.

**Objectif pédagogique** : évaluer les élèves en direct, avec des notes exploitables.

**Critères de réussite mesurables :**

1. Le professeur saisit ou importe un QCM (admin Django, JSON) sans aide.
2. Le tableau est lisible depuis le fond de la salle (gros caractères, fort contraste).
3. Chaque téléphone n'affiche que des boutons de réponse (A, B, C, D…) dans un ordre
   aléatoire, la couleur de la question et le temps restant. **Aucun énoncé n'est
   présent dans le navigateur ni dans les échanges réseau.**
4. Aucune réponse n'est perdue : sauvegarde en base, reprise après reconnexion ou
   redémarrage du serveur.
5. Une séance de 100 élèves simulés se déroule sans erreur sur le réseau prévu.

---

## 2. Utilisateurs et périmètre

| Rôle | Ce qu'il fait |
| :--- | :--- |
| Professeur | Compte distinct protégé. Configure les QCM, lance la séance, pilote le rythme, consulte et exporte les résultats. |
| Élève | Rejoint par QR code ou code de session, s'identifie, répond sur son téléphone. Voit ses statistiques si le professeur l'autorise. |
| Élève sans téléphone | Remplit un formulaire papier généré par l'application (V3). |

**Dans le périmètre** : QCM en direct, affichage tableau, affichage téléphone, identifiants
élèves, notation, mode dégradé réseau, formulaires papier, exports CSV et PDF.

**Hors périmètre (pour l'instant)** : lecture automatique des scans papier, comptes élèves
complets avec récupération de mot de passe, applications mobiles natives.

---

## 3. Déroulement d'une séance

Une séance est une suite d'**étapes** ; chaque étape affiche de 1 à 4 questions en même
temps et possède son propre minuteur.

1. Le professeur choisit un QCM et crée la séance : l'application génère un code de
   session et un QR code.
2. Les élèves rejoignent (QR code ou code), s'identifient, puis attendent dans un salon
   d'attente.
3. Le professeur démarre : l'étape 1 s'affiche au tableau, le minuteur démarre.
4. À la fin du temps, l'application passe **automatiquement** à l'étape suivante.
   Aucune correction n'est affichée par défaut.
5. À la dernière étape, la séance se termine et les résultats sont enregistrés.

**Contrôles du professeur** : pause, reprise, ajout de temps, étape suivante, étape
précédente. Le minuteur seul fait avancer la séance par défaut.

**Règles côté élève :**

- Une réponse est **définitive** : pas de modification, pas de retour aux étapes précédentes.
- Une réponse reçue après la fin du temps n'est **jamais** prise en compte.
- L'élève qui rejoint en retard arrive directement sur l'étape en cours.
- L'élève qui se déconnecte retrouve sa séance, son étape et ses réponses déjà données,
  grâce à l'état conservé en base.

---

## 4. Affichage tableau et téléphone

**Tableau (vidéoprojecteur) :**

- 1 à 4 questions côte à côte, chacune dans sa couleur, avec ses réponses possibles (A, B, C, D…).
- Minuteur de l'étape bien visible.
- Nombre de réponses reçues en temps réel.
- Gros caractères et fort contraste, lisibles depuis le fond de la salle.
- Images et formules mathématiques (KaTeX) affichées correctement.

**Téléphone (iPhone et Android, mobile first) :**

- Boutons A, B, C, D… , affichage discret de la couleur de la question et du temps restant.
- **Aucun énoncé, aucune question dans la page ni dans les échanges réseau.**
- L'élève répond à la question du tableau qui porte sa couleur.
- Un écran « réponse validée » s'affiche **uniquement** après l'accusé de réception du serveur.
- Les couleurs sont attribuées au hasard par élève, mais chaque élève répond à toutes
  les questions au fil des étapes.

**Accessibilité :**

- Daltonisme : chaque couleur est doublée d'un symbole (● ▲ ■ ◆ ★), pour ne jamais
  dépendre de la couleur seule.
- Dyslexie : police lisible (Atkinson Hyperlegible), grands espacements, pas de texte
  long sur le téléphone.
- Contraste élevé et grandes zones tactiles.

---

## 5. Questions et notation

**Contenu d'une question** : énoncé (texte, image, formule KaTeX, code), 2 à 6 choix,
durée de l'étape, identifiant unique dans le QCM.

**Types** : choix unique ou multiple. Le professeur choisit s'il l'indique aux élèves ;
par défaut, l'élève ne sait pas s'il y a une ou plusieurs bonnes réponses.

*Barème (cible, à valider — cf. §13) :**

- **Pénalité optionnelle** : le professeur peut activer ou désactiver la pénalité pour
  les mauvaises réponses, par quiz (ou par séance, à trancher en V2).
  - Pénalité **activée** : une mauvaise réponse retire des points.
  - Pénalité **désactivée** : une mauvaise réponse ne retire aucun point.
- **Note par question** : peut être **négative**. Elle est bornée entre
  `−facteur_penalite` (par défaut `−1`) et `1`.
- **Note finale de la séance** : **plafonnée à 0** (`max(0, somme_des_notes)`).
  Un élève peut avoir `−0.5` sur une question et une note finale `0`.
- **Pondération partielle** :
  `note = (bonnes cochées − facteur_penalite × mauvaises cochées) / nombre de bonnes réponses`.
  - Avec 2 bonnes réponses, cocher 1 bonne → `0.5`.
  - Avec 2 bonnes réponses, cocher 1 bonne + 1 mauvaise, pénalité activée → `0`.
  - Avec 2 bonnes réponses, cocher 1 bonne + 1 mauvaise, pénalité désactivée → `0.5`.
  - Avec 1 bonne réponse, cocher 1 mauvaise, pénalité activée → `−1`.
- **Pas de réponse** : `0` pour cette question.
- **La note n'est pas stockée** : elle est calculée par des fonctions pures testées,
  qui reçoivent leur configuration en paramètre.

**Ce que voit le professeur** (V2) : dans l'admin du quiz, une case à cocher
« Pénaliser les mauvaises réponses » et, si activée, un champ pour le facteur de
pénalité (par défaut `1.0`). La note finale affichée dans les exports est toujours
`max(0, somme)`.

**Format JSON d'import (point de départ, à ajuster en V1) :**

```json
{
  "titre": "CM 3 - Exemple",
  "questions": [
    {
      "uid": "Q1",
      "etape": 1,
      "duree_s": 60,
      "enonce": "Quelle est la complexité de la recherche dichotomique ?",
      "type": "unique",
      "choix": [
        {"lettre": "A", "texte": "O(n)", "correct": false},
        {"lettre": "B", "texte": "O(log n)", "correct": true}
      ]
    }
  ]
}
```

---

## 6. Identifiants et anti-usurpation

- Chaque élève a un identifiant et un code personnel (PIN) fournis par le professeur ;
  **un seul appareil actif** par élève à la fois.
- Import CSV de la liste de classe (nom, prénom) : l'application génère identifiant et
  PIN, et produit une liste imprimable.
- Données stockées : **prénom et nom uniquement** (minimum nécessaire).
- Une nouvelle connexion remplace l'ancienne ; le professeur voit qui est connecté et
  peut réinitialiser l'appareil d'un élève.
- V0 et V1 : un simple code de session suffit pour la démonstration.
- Les identifiants de questions (`uid`) sont uniques par QCM, stables, repris
  discrètement sur le tableau et sur le papier.

---

## 7. Architecture technique (résumé — détail dans `ARCHITECTURE.md`)

| Sujet | Choix retenu |
| :--- | :--- |
| Temps réel | Polling d'un endpoint léger `/etat/` toutes les 1 à 2 s, avec petit délai aléatoire |
| Minuteur | Le serveur stocke `ends_at` ; le client affiche un décompte local à partir de l'heure serveur |
| Base | SQLite (WAL) en dev/démo, PostgreSQL pour l'école — ORM uniquement |
| Front | Templates Django + HTMX + JS simple, KaTeX pour les formules |
| Hébergement | Serveur de l'école ; mode serveur local possible (plan B réseau) |
| Admin | Admin Django pour saisir les questions dès la V1 |

---

## 8. Réseau et mode dégradé

**Coupure réseau pendant la séance (V1) :**

- Le téléphone stocke chaque réponse dans `localStorage` avec un `id_client` unique et
  la renvoie automatiquement, avec espacement progressif des tentatives.
- Le serveur ignore les doublons grâce à `id_client`.
- L'élève voit « envoyé » ou « en attente ». « Réponse validée » n'apparaît qu'après
  l'accusé de réception du serveur.
- **Règle stricte** : une réponse qui arrive après `ends_at` n'est pas prise en compte.
- V3 (option) : acceptation de réponses tardives horodatées avant la fin, signalées
  « à valider » au professeur.

**Mode papier (V3) :**

- PDF personnalisé par élève (énoncés et réponses mélangés, identifiant imprimé, QR code).
- Les identifiants de questions servent à réconcilier papier et application.
- Lecture automatique des scans : hors périmètre. Saisie manuelle ou import CSV d'abord.
- **Fusion papier / appli, question par question** : si l'élève a une réponse enregistrée
  dans l'application pour cette question, elle prime ; sinon, on prend la réponse papier.

---

## 9. Sécurité, confidentialité et données personnelles

**Règle centrale : les énoncés et les bonnes réponses ne quittent jamais le serveur
vers les téléphones.**

- Les endpoints élèves ne renvoient jamais énoncés, textes de choix ni `est_correct`.
  Ils renvoient seulement : couleur, nombre de choix, temps restant, accusé de réception.
- La page tableau et l'interface professeur sont réservées au compte professeur.
- La note est calculée uniquement côté serveur.
- Un test automatique parcourt toutes les réponses JSON des endpoints élèves et vérifie
  l'absence de ces champs (cf. `AGENTS.md` §1).
- Une réponse après `ends_at` est refusée ; une seconde réponse à la même question est refusée.
- Données personnelles : prénom, nom, identifiant, réponses. Aucune autre donnée.
- Conservation : commande de purge à la fin de l'année universitaire (durée à valider
  avec le DPO de l'INSA).

---

## 10. Résultats et exports

| Résultat | Contenu | Export |
| :--- | :--- | :--- |
| Note par élève | Total de la séance selon le barème | CSV, PDF |
| Détail par question | Réponse donnée, réponse attendue, points obtenus | CSV, PDF |
| Taux de réussite par question | Part des élèves ayant répondu correctement | CSV, PDF |
| Statistiques élèves | Visibles par l'élève après la séance, si activé par le professeur | Affichage |

Les réponses papier sont marquées `source = papier` dans les exports.
Les statistiques de classe au tableau en fin d'étape sont une option ultérieure (V4).

---

## 11. Plan de versions (résumé — détail dans `ROADMAP.md`)

| Version | Contenu | Terminé quand |
| :--- | :--- | :--- |
| **V0** (démo) | QCM codé en dur, écran prof/tableau, écran élève, minuteur serveur, récupération réponse | 3 téléphones rejoignent et répondent, réponse tardive refusée |
| **V1** (cœur) | Admin Django, import JSON, QR + code session, 1 à 4 questions colorées, pause/+temps/suivant/précédent, reconnexion, file locale, KaTeX, images | Séance de 5 étapes avec redémarrage serveur au milieu, sans perte |
| **V2** (comptes et notes) | Import CSV,JSON, PDF élèves, identifiant + PIN, un appareil actif, notation, résultats, accessibilité | Notes couvertes par tests, taux de réussite exact |
| **V3** (papier et exports) | PDF par élève, saisie manuelle papier, fusion, exports CSV/PDF, stats élèves | Feuille papier + séance appli fusionnent sans doublon |
| **V4** (finitions) | Stats au tableau, serveur local, test de charge 100 clients, purge, doc finale | Test de charge sans erreur, guide remis |

---

## 12. Méthode de développement (vibe coding)

Voir `AGENTS.md` pour les règles impératives. Résumé :

- Un ticket = une branche = un périmètre fermé ; plan validé avant code.
- Tests d'abord sur : notation, minuteur, refus tardif, absence d'énoncé dans les endpoints.
- `JOURNAL.md` à chaque session ; `docs/decisions/` pour les choix structurants ;
  `prompts/` pour les prompts clés (succès et échecs).
- Hooks pre-commit : `ruff` + `pytest`. CI GitHub Actions à chaque push.
- Tag Git à chaque version qui fonctionne.

---



