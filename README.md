# QCM en direct

Application web Django pour faire répondre une classe à un QCM projeté au
tableau. Les élèves répondent depuis leur téléphone **sans jamais voir
l'énoncé** ; le serveur est la seule référence temporelle.

Ce dépôt couvre la V1 (ticket #1 et dette #3), la V2 (comptes, groupes,
notes) et la V3 (banque de questions, import et sélection) :

- import JSON d'un QCM (format `docs/SPEC.md`) et saisie via l'admin ;
- code de session + QR code, salon d'attente ;
- 1 à 4 questions par étape, une couleur et un symbole par question ;
- couleur, symbole et graine de mélange persistés par élève ;
- passage automatique à l'étape suivante à `ends_at`, pause / reprise /
  +temps / suivant / précédent ;
- polling `/api/etat/` toutes les 1 à 2 s, file locale `localStorage` et
  anti-doublon `id_client` ;
- tableau professeur protégé, questions en pleine largeur, compteurs de
  réponses et de participants discrets en pied de page, KaTeX et images ;
- création de séance via `/session/creer/`, QR code sur la page initiale et
  sur le tableau en attente ;
- bouton « Terminer la séance » sur le tableau et sur le téléphone ;
- libellés français et colonne « Groupe » dans la vue Participants ;
- tests du refus tardif, du doublon, de la reconnexion et de l'absence de
  fuite d'énoncé ;
- V2 : comptes élèves sans PIN, import CSV/JSON (interface Groupe et CLI),
  rotation des questions par blocs, mode Présentation et écran de pré-séance ;
- V3 : banque de questions par professeur (`QuestionSet`), import JSON/CSV de
  questions, sélection ordonnée par QCM et durée par question.

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

1. Se connecter à l'admin (`/admin/`), puis ouvrir `/session/creer/` (ou le
   bouton « Créer une séance » de l'accueil) et choisir le QCM importé.
2. La page initiale affiche le code et le QR code ; cliquer sur « Ouvrir le
   tableau ». Le QR code n'est affiché que sur cette page.
3. Les élèves scannent le QR code (ou ouvrent `/rejoindre/` et saisissent le
   code), puis répondent.
4. Démarrer la séance. Le tableau affiche l'étape, les questions colorées et
   les compteurs ; les téléphones n'affichent que les lettres.
5. Couper puis relancer `runserver` au milieu de la séance : les réponses
   déjà reçues restent en base et la séance reprend à la même étape.
6. Utiliser Pause / Reprendre / +30 s / +1 min / +2 min / Précédent / Suivant,
   et « Terminer la séance » pour clôturer et revenir à l'accueil.

## V2 — comptes, groupes et import

- Le professeur crée un groupe dans l'admin (`Groupe`), puis importe ses
  élèves depuis `/groupe/<id>/importer-eleves/` (CSV `nom,prenom` ou JSON
  `[{"nom": "…", "prenom": "…"}]`). La commande
  `python manage.py import_participants <fichier> --groupe <nom>` reste
  disponible (recherche du groupe insensible à la casse).
- L'import génère un identifiant lisible et unique (`MARIE-DUP32`), sans PIN.
  La liste CSV/JSON des identifiants est téléchargeable depuis la même page.
- La séance est rattachée à un groupe à la création ; les élèves rejoignent
  avec l'identifiant affiché sur l'écran de pré-séance.
- Les questions sont regroupées en paquets de 4 ; un paquet de T questions
  génère T étapes (rotation de la couleur), pour que chaque élève réponde à
  toutes les questions du paquet.
- Le tableau propose un « Mode Présentation » plein écran (questions, timer et
  compteurs, sans contrôles).

## V3 — banque de questions et sélection

- Admin → « Ensembles de questions » : le professeur crée ses ensembles, saisit
  les questions et leurs choix, et importe un fichier depuis le lien
  « Importer » de chaque ensemble (ou `/ensemble/<id>/importer-questions/`).
- Import JSON : `{"questions": [{"uid": "Q1", "enonce": "…", "type":
  "unique", "duree_s": 60, "choix": [...]}]}`. La racine peut aussi être une
  liste ; les anciens champs `titre` et `etape` sont ignorés. Import CSV : une
  ligne par choix, en-tête
  `uid,enonce,type,lettre,texte,correct[,duree_s]`. Exemples :
  `examples/questions_demo.json` et `examples/questions_demo.csv`.
- Sur la page d'un QCM, le bouton « Sélectionner les questions » ouvre un
  panier groupé par ensemble : cocher puis « Ajouter au Quiz » ajoute à la fin
  dans l'ordre choisi ; la page du QCM affiche la liste courante et permet de
  retirer une question.
- `Quiz.duree_s` (60 s par défaut) est une durée minimale d'étape ;
  `Question.duree_s` permet d'allonger une question complexe. Une étape dure
  le maximum entre la durée du QCM et celles des questions du paquet.
- La commande historique
  `python manage.py import_quiz examples/quiz_demo.json --proprietaire <user>`
  reste disponible : elle crée un ensemble et un QCM qui sélectionne toutes
  les questions du fichier.

## Accès depuis un téléphone (Wi-Fi local)

1. Connecter le serveur et le téléphone au **même réseau Wi-Fi** (éviter un
   réseau invité qui isole les appareils).
2. Lancer le serveur sur toutes les interfaces :
   `python manage.py runserver 0.0.0.0:8000`.
3. Trouver l'adresse IP locale du serveur :
   - macOS : `ipconfig getifaddr en0` (ou `en1` selon l'interface) ;
   - Linux : `hostname -I` ;
   - Windows : `ipconfig`, ligne « Adresse IPv4 ».
4. Depuis Safari ou Chrome sur le téléphone, ouvrir
   `http://192.168.x.x:8000/rejoindre/` en remplaçant l'adresse par celle
   trouvée, ou scanner le QR code affiché sur la page initiale ou sur le
   tableau en attente.
5. Si macOS le demande, autoriser Python à recevoir des connexions entrantes
   (pare-feu).
6. `ALLOWED_HOSTS` : avec `DEBUG=1` (défaut en démonstration), toutes les
   adresses sont acceptées. Avec `DEBUG=0`, définir
   `DJANGO_ALLOWED_HOSTS="192.168.x.x,localhost"` ; les adresses IPv4 locales
   détectées sont ajoutées automatiquement.
7. **QR code et `QCM_LAN_HOST`** : par défaut, le QR code encode l'URL de la
   requête (`http://127.0.0.1:8000/...`), inutilisable depuis un téléphone car
   `127.0.0.1` désigne le téléphone lui-même. Pour que le QR code et l'URL
   affichée sous celui-ci pointent vers le serveur, définir l'adresse LAN
   trouvée à l'étape 3 :
   ```bash
   QCM_LAN_HOST=192.168.1.42:8000 python manage.py runserver 0.0.0.0:8000
   ```
   Le QR code encode alors `http://192.168.1.42:8000/rejoindre/<code>/`. Le
   tableau affiche aussi le QR et le code pendant l'attente, pour que
   « Ouvrir » depuis l'admin soit directement utilisable.

Ne pas exposer ce serveur de démonstration sur Internet : il est prévu pour le
réseau local et n'utilise pas HTTPS.

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
- **Rotation par paquets (V2)** : les questions sont regroupées par paquets de
  4 ; un paquet de T questions génère T étapes et la couleur de l'élève tourne
  à chaque étape, pour qu'il réponde à toutes les questions du paquet.
- **Tolérance de latence : 0 s.** Une réponse reçue après `ends_at` est refusée.
- Format JSON : `titre` + `questions[]` avec `uid`, `duree_s`, `enonce`,
  `type`, `choix[]` (`lettre`, `texte`, `correct`). Le champ `etape` reste
  accepté mais n'est plus utilisé : les questions sont lues dans l'ordre du
  fichier et regroupées par paquets de 4 ; la durée du paquet est celle de sa
  première question.

Les ADR correspondants sont dans `docs/decisions/`.

## Dépendances ajoutées

- `Django==6.1.3` — framework imposé par `AGENTS.md`.
- `qrcode==8.2` — génération du QR code en SVG. La bibliothèque standard ne
  produit pas de QR code ; le rendu SVG évite d'ajouter Pillow.
- `pytest==9.2.0`, `pytest-django==4.14.0`, `ruff==0.17.4` — tests et lint
  imposés par `AGENTS.md`.

## Limites connues de la V1

- La V2 couvre les comptes élèves, les groupes, l'import et la notation ; les
  exports CSV/PDF et le papier restent en V3.
- KaTeX est chargé depuis un CDN sur la page tableau ; hors ligne, les
  formules s'affichent en texte brut. Le reste de l'application fonctionne.
- Le QR code est un SVG généré à la volée, sans stockage.
- La file locale a été vérifiée de bout en bout : coupure du serveur, clic,
  « En attente du réseau… », redémarrage, reprise et accusé serveur ; le
  serveur est couvert par les tests (idempotence `id_client`,
  `(participant, question)` unique).
