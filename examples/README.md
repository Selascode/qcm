# Exemples de données

## Groupe d'élèves (V2)

`groupe_demo.csv` et `groupe_demo.json` contiennent les 6 élèves du groupe
« ISIA4 » utilisé dans les captures. Ces fichiers sont acceptés par l'interface
web d'import et par la commande `manage.py import_participants`.

### Créer le groupe et importer

1. Lancer le serveur : `python manage.py runserver 0.0.0.0:8000`.
2. Se connecter à l'admin : `http://127.0.0.1:8000/admin/login/` avec le compte
   professeur propriétaire.
3. Créer le groupe : « Groupes » → « Ajouter » (`/admin/qcm/groupe/add/`), nom
   `ISIA4`, propriétaire = le professeur connecté, puis enregistrer.
4. Dans la liste des groupes (`/admin/qcm/groupe/`), cliquer sur « Importer »
   dans la ligne du groupe. La page s'ouvre à
   `/groupe/<id>/importer-eleves/` ; l'`<id>` est le `pk` du groupe, visible
   dans l'URL de la fiche `/admin/qcm/groupe/<id>/change/`.
5. Déposer `groupe_demo.csv` (en-tête `nom,prenom`) ou `groupe_demo.json`
   (liste d'objets `{nom, prenom}`), puis « Importer ». La page affiche le
   résumé et les identifiants générés ; les boutons « Télécharger CSV/JSON »
   exportent la liste.
6. Seul le propriétaire du groupe peut ouvrir cette page : un autre professeur
   authentifié reçoit une 404, un visiteur anonyme est redirigé vers la
   connexion.

### Ligne de commande

```bash
python manage.py import_participants examples/groupe_demo.csv --groupe ISIA4
# ou
python manage.py import_participants examples/groupe_demo.json --groupe ISIA4
```

Les identifiants sont générés au format `PRENOM-NOMnn` (ex. `MARIE-DUP00`),
sans PIN.

### Capture

`docs/screenshots/v2-corrections/apres-import.png` montre la page d'import du
groupe `ISIA4` (id 1 dans la base de démonstration) avec le formulaire et les
liens d'export. Pour ouvrir la capture en local : `xdg-open` (Linux) ou `open`
(macOS) sur ce fichier, ou la consulter dans la PR #6.
