# QCM en direct — V1

Application web Django pour faire répondre une classe à un QCM projeté au
tableau. Les élèves répondent depuis leur téléphone **sans jamais voir
l'énoncé** ; le serveur est la seule référence temporelle.

Cette branche implémente le périmètre V1 du ticket #1 :

- import JSON d'un QCM (format `docs/SPEC.md` §5) et saisie via l'admin ;
- code de session + QR code, salon d'attente ;
- 1 à 4 questions par étape, une couleur et un symbole par question ;
- couleur, symbole et graine de mélange persistés par élève ;
- passage automatique à l'étape suivante à `ends_at`, pause / reprise /
  +temps / suivant / précédent ;
- polling `/api/etat/` toutes les 1 à 2 s, file locale `localStorage` et
  anti-doublon `id_client` ;
- tableau professeur protégé, compteurs de réponses en temps réel, KaTeX et
  images ;
- tests du refus tardif, du doublon, de la reconnexion et de l'absence de
  fuite d'énoncé.

## Installation (dev / démo)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

Importer le QCM de démonstration :

```bash
python manage.py import_quiz examples/quiz_demo.json --proprietaire <utilisateur>
```

## Déroulé de démonstration

1. Dans l'admin (`/admin/`), créer une **séance** en choisissant le QCM importé.
2. Ouvrir le lien « Tableau » de la séance ; le code et le QR code s'affichent.
3. Les élèves scannent le QR code (ou ouvrent `/rejoindre/` et saisissent le
   code), puis répondent.
4. Démarrer la séance. Le tableau affiche l'étape, les questions colorées et
   les compteurs ; les téléphones n'affichent que les lettres.
5. Couper puis relancer `runserver` au milieu de la séance : les réponses
   déjà reçues restent en base et la séance reprend à la même étape.
6. Utiliser Pause / Reprendre / +30 s / +1 min / +2 min / Précédent / Suivant.

Pour un accès depuis les téléphones du réseau local, lancer
`python manage.py runserver 0.0.0.0:8000` et ouvrir l'URL IP du serveur.

## Tests et qualité

```bash
pytest
ruff check .
```

Le test `qcm/tests/test_parcours_v1.py` exécute le critère de fin V1 : cinq
étapes, quatre élèves, un redémarrage simulé par fermeture/réouverture des
connexions au milieu, puis vérifie qu'aucune réponse n'est perdue.

## Choix V1

- **Quatre couleurs** (`#C62828`, `#1565C0`, `#2E7D32`, `#6A1B9A`), chacune
  doublée d'un symbole (● ▲ ■ ◆), pour ne pas dépendre de la couleur seule.
- Avec quatre questions dans une étape, chaque couleur tombe sur sa colonne ;
  avec moins de questions, la couleur est repliée modulo le nombre de
  questions pour que chaque élève ait toujours une question à traiter.
- **Tolérance de latence : 0 s.** Une réponse reçue après `ends_at` est refusée.
- Format JSON figé : `titre` + `questions[]` avec `uid`, `etape`, `duree_s`,
  `enonce`, `type`, `choix[]` (`lettre`, `texte`, `correct`). La durée est
  portée par l'étape ; toutes les questions d'une même étape doivent annoncer
  la même `duree_s`.

Les ADR correspondants sont dans `docs/decisions/`.

## Dépendances ajoutées

- `Django==6.1.3` — framework imposé par `AGENTS.md`.
- `qrcode==8.2` — génération du QR code en SVG. La bibliothèque standard ne
  produit pas de QR code ; le rendu SVG évite d'ajouter Pillow.
- `pytest==9.2.0`, `pytest-django==4.14.0`, `ruff==0.17.4` — tests et lint
  imposés par `AGENTS.md`.

## Limites connues de la V1

- Les comptes élèves, le PIN, la notation, les exports et le papier sont
  hors périmètre (V2/V3).
- KaTeX est chargé depuis un CDN sur la page tableau ; hors ligne, les
  formules s'affichent en texte brut. Le reste de l'application fonctionne.
- Le QR code est un SVG généré à la volée, sans stockage.
- La file locale a été vérifiée de bout en bout : coupure du serveur, clic,
  « En attente du réseau… », redémarrage, reprise et accusé serveur ; le
  serveur est couvert par les tests (idempotence `id_client`,
  `(participant, question)` unique).
