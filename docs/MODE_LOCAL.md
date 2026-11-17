# Mode serveur local — hotspot Wi-Fi du professeur

Ce guide explique comment faire fonctionner l'application QCM **sans dépendre
du Wi-Fi de l'école** : un ordinateur portable crée son propre réseau Wi-Fi,
les téléphones s'y connectent, et le serveur Django tourne sur ce réseau
isolé. C'est la solution recommandée lorsque le Wi-Fi de l'établissement est
saturé, filtré, ou isole les appareils entre eux.

> **Principe.** Le portable est à la fois le serveur et la borne Wi-Fi. Le
> réseau n'a pas besoin d'Internet : seuls les téléphones et le portable
> doivent se joindre. Aucun câble, aucun routeur supplémentaire n'est
> nécessaire.

---

## 1. Ce qu'il faut avant de commencer

- Un ordinateur portable dont la carte Wi-Fi **peut créer un point d'accès**
  (la plupart des cartes récentes le peuvent ; sous Linux, vérifier avec
  `iw list`).
- Les téléphones des élèves, avec le Wi-Fi activé.
- L'application installée sur le portable :

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  python manage.py migrate
  python manage.py createsuperuser
  ```

  Sous Windows, l'activation est `.venv\Scripts\activate`.

- Le portable branché sur secteur : le partage de connexion et l'écran
  consommèrent de la batterie.

> **Pas d'Internet ?** Ce n'est pas un problème pour l'application. Les
> téléphones afficheront parfois « Ce réseau n'a pas d'accès Internet » :
> garder la connexion et refuser le basculement automatique vers un autre
> réseau.

> **Attention.** Windows et macOS demandent parfois une connexion « amont »
> active pour activer le partage de connexion. Si le portable n'a aucune
> connexion (ni Wi-Fi, ni Ethernet), ces deux systèmes peuvent refuser de
> créer le hotspot ; dans ce cas, brancher le portable en Ethernet, utiliser
> un petit routeur, ou passer par Linux (`ipv4.method shared` fonctionne sans
> Internet).

---

## 2. Créer le hotspot

Choisir la procédure correspondant au système du portable. Noter ensuite
l'**adresse IPv4 du portable sur le hotspot** : elle servira pour
`QCM_LAN_HOST` et pour l'URL à distribuer.

### 2.1. Windows 10 / 11

1. Ouvrir **Paramètres → Réseau et Internet → Partage de connexion mobile**
   (ou **Point d'accès mobile**).
2. Choisir la connexion à partager (Wi-Fi, Ethernet ou aucune selon la
   version de Windows), puis **Modifier** pour définir le nom du réseau
   (par exemple `QCM-INSA`) et un mot de passe d'au moins 8 caractères.
3. Activer **Partager ma connexion Internet**.
4. Ouvrir une invite de commandes et lancer `ipconfig`. Repérer la carte
   correspondant au partage (souvent « Local Area Connection* » ou
   « Microsoft Wi-Fi Direct Virtual Adapter ») et son **Adresse IPv4** :
   c'est généralement `192.168.137.1`.
5. Dans le pare-feu Windows, autoriser les connexions entrantes sur le
   port 8000 pour les réseaux **privés**. En PowerShell administrateur :

   ```powershell
   New-NetFirewallRule -DisplayName "QCM 8000" -Direction Inbound `
     -LocalPort 8000 -Protocol TCP -Action Allow
   ```

> Si le partage de connexion mobile n'est pas disponible, certains pilotes
> acceptent encore l'ancienne commande `netsh wlan set hostednetwork` ; elle
> est dépréciée et dépend du pilote. Le partage via les Paramètres est la
> voie normale.

### 2.2. macOS

1. Ouvrir **Réglages Système → Général → Partage → Partage Internet**.
2. Choisir la source à partager (Ethernet, Thunderbolt, etc.) et cocher
   **Wi-Fi** comme destination. Le partage « Wi-Fi vers Wi-Fi » n'est pas
   possible : si le portable n'a qu'une connexion Wi-Fi, utiliser une source
   filaire ou un petit routeur.
3. Cliquer sur **Options Wi-Fi…** : nom du réseau (par exemple `QCM-INSA`),
   canal, et sécurité **WPA2/WPA3 Personnel** avec un mot de passe.
4. Cocher le partage. L'interface du hotspot est généralement `bridge100` ;
   son adresse se lit avec :

   ```bash
   ipconfig getifaddr bridge100
   ```

   Elle est souvent `192.168.2.1`.
5. Autoriser Python à recevoir des connexions dans **Réglages Système →
   Réseau → Pare-feu** (ou désactiver le pare-feu le temps de la séance,
   uniquement sur ce réseau local).

### 2.3. Linux (NetworkManager)

**Le nom de l'interface Wi-Fi n'est pas toujours `wlan0`.** Sur les portables
récents, c'est souvent `wlo1`, `wlp2s0`, `wlp3s0`, etc. Ne pas recopier
`wlan0` au hasard : le premier travail est de relever le vrai nom.

1. Trouver l'interface Wi-Fi :

   ```bash
   nmcli -f DEVICE,TYPE,STATE device status
   # ou
   iw dev
   ```

   Prendre la ligne de type `wifi` qui n'est pas `p2p-dev-...` (par exemple
   `wlo1`) et la garder dans une variable :

   ```bash
   INTERFACE_WIFI=wlo1   # remplacer par le nom relevé
   ```

2. Vérifier que la carte accepte le mode AP :

   ```bash
   iw list | grep -A 5 "Supported interface modes"
   ```

   La liste doit contenir `AP`. Si ce n'est pas le cas, utiliser un routeur
   portable ou une clé Wi-Fi compatible.

3. Créer le hotspot avec le bon nom d'interface :

   ```bash
   nmcli device wifi hotspot ifname "$INTERFACE_WIFI" \
     ssid QCM-INSA password "motdepasse123"
   ```

   NetworkManager active alors un partage IPv4 et attribue généralement
   l'adresse `10.42.0.1` au portable. Vérifier avec :

   ```bash
   ip -4 addr show "$INTERFACE_WIFI"
   ```

4. Si la commande directe échoue, créer la connexion explicitement. Avant
   cela, supprimer un éventuel ancien profil créé avec un mauvais nom
   d'interface (`wlan0`, par exemple) :

   ```bash
   nmcli connection delete qcm-hotspot 2>/dev/null
   nmcli connection add type wifi ifname "$INTERFACE_WIFI" \
     con-name qcm-hotspot autoconnect no ssid QCM-INSA \
     802-11-wireless.mode ap 802-11-wireless.band bg \
     ipv4.method shared
   nmcli connection modify qcm-hotspot \
     wifi-sec.key-mgmt wpa-psk wifi-sec.psk "motdepasse123"
   nmcli connection up qcm-hotspot
   ```

   L'erreur `No suitable device found ... mismatching interface name`
   signifie que le profil a été créé avec un autre `ifname` que celui de la
   carte : le supprimer et le recréer avec `$INTERFACE_WIFI`.

5. Ouvrir le pare-feu (une seule des deux commandes suffit selon le système) :

   ```bash
   sudo ufw allow 8000/tcp
   # ou, si firewalld est installé :
   sudo firewall-cmd --add-port=8000/tcp --permanent
   sudo firewall-cmd --reload
   ```

   Si `firewall-cmd` n'existe pas, c'est que firewalld n'est pas installé :
   la règle `ufw` suffit.

> **Sans Internet, le partage fonctionne quand même** avec
> `ipv4.method shared` : NetworkManager crée un réseau local et un serveur
> DHCP, sans dépendre d'une connexion amont.

---

## 3. Lancer l'application sur le hotspot

Remplacer `192.168.137.1` par l'adresse trouvée à l'étape 2, et `8000` par
le port choisi.

### Linux / macOS

```bash
QCM_LAN_HOST=192.168.137.1:8000 python manage.py runserver 0.0.0.0:8000
```

### Windows PowerShell

```powershell
$env:QCM_LAN_HOST="192.168.137.1:8000"
python manage.py runserver 0.0.0.0:8000
```

### Windows (invite de commandes)

```bat
set QCM_LAN_HOST=192.168.137.1:8000
python manage.py runserver 0.0.0.0:8000
```

`QCM_LAN_HOST` est l'adresse que le **téléphone** doit utiliser. Le QR code
et l'URL affichée sous le QR code pointent alors vers
`http://192.168.137.1:8000/rejoindre/<code>/`.

- Laisser le terminal ouvert pendant toute la séance.
- Sur le portable, ouvrir l'application avec `http://127.0.0.1:8000/`.
- Si `DEBUG=0`, ajouter l'adresse au serveur :

  ```bash
  QCM_LAN_HOST=192.168.137.1:8000 \
  DJANGO_ALLOWED_HOSTS=192.168.137.1,localhost \
  python manage.py runserver 0.0.0.0:8000
  ```

- **Ne pas modifier le code pendant la séance** : `runserver` recharge
  l'application et coupe brièvement les requêtes.

---

## 4. Distribuer l'adresse aux élèves

1. Créer la séance dans l'application, puis ouvrir la **page initiale** de
   la séance. Elle affiche le code de session et le QR code.
2. Projeter cette page (ou le tableau en attente) : les élèves scannent le
   QR code avec l'appareil photo.
3. Sans QR code, écrire au tableau l'adresse complète et le code :

   ```text
   http://192.168.137.1:8000/rejoindre/
   Code de session : ABC123
   ```

4. Faire un test avec **un téléphone** avant de distribuer l'adresse à toute
   la classe : ouvrir l'URL, vérifier que la page de connexion s'affiche.
5. L'adresse IP du hotspot peut changer après un redémarrage du portable ou
   du partage. La vérifier à chaque séance et relancer le serveur avec la
   nouvelle valeur.

> **Le QR code est la méthode la plus fiable.** Il évite les fautes de
> frappe et fonctionne sans Internet. L'URL sous le QR code permet de
> vérifier l'adresse encodée.

---

## 5. Capacité et bonnes pratiques pour une classe

- **100 téléphones** : le hotspot d'un portable suffit pour une salle, mais
  rester à proximité, préférer la bande **2,4 GHz** (meilleure portée) et un
  canal peu encombré (1, 6 ou 11).
- Brancher le portable sur secteur, désactiver la mise en veille et fermer
  les applications gourmandes en réseau.
- L'application interroge le serveur toutes les 1 à 2 secondes. Avec 100
  téléphones, cela représente quelques dizaines de requêtes par seconde :
  c'est prévu, mais un serveur de développement `runserver` a une file
  d'attente de connexion limitée. Le script `scripts/test_charge.py` étale
  légèrement les connexions pour cette raison. Pour une salle complète, il
  est plus robuste de lancer l'application avec un serveur WSGI de
  production (par exemple Gunicorn sous Linux) ; ce n'est pas nécessaire
  pour la démonstration.
- Demander aux élèves de **désactiver l'itinérance automatique** vers le
  Wi-Fi de l'école, sinon le téléphone peut quitter le hotspot en cours de
  séance.
- Éviter les réseaux invités qui isolent les appareils : le hotspot du
  portable, lui, laisse les téléphones joindre le serveur.

---

## 6. Dépannage

| Symptôme | Piste à vérifier |
| :--- | :--- |
| Le téléphone ne voit pas le réseau | Le hotspot est actif ; le portable est à portée ; la carte Wi-Fi supporte le mode AP ; le canal est autorisé dans le pays. |
| `Device "wlan0" does not exist` ou « n'est pas un périphérique Wi-Fi » | Le nom `wlan0` n'est qu'un exemple : relever le vrai nom avec `nmcli -f DEVICE,TYPE,STATE device status` (souvent `wlo1` ou `wlp2s0`) et le passer à `ifname`. |
| `No suitable device found ... mismatching interface name` | Le profil `qcm-hotspot` a été créé avec un mauvais `ifname` : `nmcli connection delete qcm-hotspot`, puis le recréer avec l'interface relevée. |
| `firewall-cmd: command not found` | firewalld n'est pas installé ; la règle `sudo ufw allow 8000/tcp` suffit sur Ubuntu. |
| Le téléphone se connecte mais la page ne s'ouvre pas | L'URL utilise bien l'adresse du hotspot (pas `127.0.0.1`) ; le serveur écoute sur `0.0.0.0:8000` ; le pare-feu autorise le port 8000. |
| `QCM_LAN_HOST` ne change rien | Le serveur a été relancé après la modification ; la page de la séance a été rouverte pour régénérer le QR code. |
| Le QR code contient `127.0.0.1` | `QCM_LAN_HOST` n'était pas défini au lancement ; le définir puis relancer. |
| Un téléphone bascule sur le Wi-Fi de l'école | Oublier/supprimer le réseau de l'école sur le téléphone ou désactiver l'itinérance automatique le temps de la séance. |
| « Ce réseau n'a pas d'accès Internet » | Normal : garder la connexion, refuser le basculement. L'application n'a pas besoin d'Internet. |
| Les téléphones se déconnectent tous en même temps | Le portable s'est mis en veille, le hotspot a redémarré, ou la carte Wi-Fi a changé de canal ; vérifier l'alimentation et relancer le partage. |
| L'adresse IP a changé | La relire (`ipconfig`, `ipconfig getifaddr`, `ip -4 addr`) et relancer avec la nouvelle valeur `QCM_LAN_HOST`. |
| Un autre appareil du réseau ne doit pas voir l'application | Le hotspot est un réseau local : ne pas le laisser ouvert sur un lieu public ; arrêter le partage et le serveur après la séance. |

---

## 7. Sécurité

- L'application est servie en **HTTP**, sans TLS : elle est prévue pour un
  réseau local isolé, jamais pour Internet.
- Le hotspot ne doit pas être partagé au-delà de la salle ; utiliser un mot
  de passe Wi-Fi et couper le partage après la séance.
- L'accès professeur reste protégé par le compte Django ; verrouiller le
  portable pendant les pauses.
- Les données personnelles (noms, réponses) restent dans la base locale du
  portable ; sauvegarder `db.sqlite3` après la séance si nécessaire.

---

## 8. Après la séance : déconnecter et remettre en état

À la fin de la séance, remettre le portable dans son état habituel. Ces
opérations ne suppriment aucune réponse : la base `db.sqlite3` reste dans le
dossier du projet.

### 8.1. Arrêter l'application

Dans le terminal du serveur, faire `Ctrl+C`. Vérifier qu'il ne reste pas de
processus :

```bash
ps aux | grep "manage.py runserver"
```

Fermer le terminal. Si un processus persiste : `pkill -f "manage.py runserver"`
(à ne faire qu'après avoir vérifié qu'il s'agit bien de ce serveur).

### 8.2. Arrêter le hotspot

- **Windows** : Paramètres → Réseau et Internet → Partage de connexion mobile
  → désactiver. Si l'ancienne commande `netsh` a été utilisée :
  `netsh wlan stop hostednetwork` (invite administrateur).
- **macOS** : Réglages Système → Général → Partage → décocher **Partage
  Internet**.
- **Linux** : repérer le profil actif puis le désactiver :

  ```bash
  nmcli -f NAME,DEVICE connection show --active
  nmcli connection down qcm-hotspot   # ou le nom affiché
  ```

  Si le profil `qcm-hotspot` a été créé uniquement pour le test, le supprimer :

  ```bash
  nmcli connection delete qcm-hotspot
  ```

  Ne pas supprimer un profil Wi-Fi existant qui sert habituellement au
  portable. La commande directe `nmcli device wifi hotspot` peut avoir créé
  un profil nommé `Hotspot` : utiliser le nom affiché par `connection show
  --active`.

### 8.3. Reconnecter le Wi-Fi habituel

- **Windows / macOS** : rouvrir le menu Wi-Fi et se reconnecter au réseau
  habituel (école, maison, etc.).
- **Linux** :

  ```bash
  nmcli device wifi list
  nmcli device wifi connect "<SSID>" password "<mot-de-passe>"
  # ou, si le profil existe déjà :
  nmcli connection up "<nom-du-profil>"
  nmcli -f NAME,DEVICE connection show --active
  ```

  Le portable était peut-être connecté en Wi-Fi avant de passer en mode
  point d'accès : il faut le reconnecter explicitement.

### 8.4. Remettre le pare-feu

La règle ouverte pour la démonstration peut être retirée si elle n'est plus
utile. Le serveur n'écoute plus après l'arrêt, mais la règle resterait
ouverte pour les prochaines fois.

- **Ubuntu / ufw** :

  ```bash
  sudo ufw status
  sudo ufw delete allow 8000/tcp
  sudo ufw reload
  sudo ufw status
  ```

  Si `ufw delete allow 8000/tcp` ne trouve pas la règle, afficher les règles
  numérotées (`sudo ufw status numbered`) et supprimer le bon numéro
  (`sudo ufw delete <numéro>`).

- **firewalld** :

  ```bash
  sudo firewall-cmd --remove-port=8000/tcp --permanent
  sudo firewall-cmd --reload
  sudo firewall-cmd --list-ports
  ```

- **Windows** (PowerShell administrateur) :

  ```powershell
  Get-NetFirewallRule -DisplayName "QCM 8000"
  Remove-NetFirewallRule -DisplayName "QCM 8000"
  ```

  Si Python a été autorisé interactivement lors du premier lancement, le
  retirer dans **Sécurité Windows → Pare-feu et protection du réseau →
  Autoriser une application via le pare-feu**. Laisser la règle si
  l'application doit resservir.

- **macOS** : Réglages Système → Réseau → Pare-feu → Options ; retirer Python
  de la liste des applications autorisées, ou réactiver le pare-feu s'il a
  été désactivé pour la séance.

### 8.5. Côté élèves et données

- Demander aux élèves de **revenir sur leur Wi-Fi habituel** et, si
  nécessaire, d'oublier le réseau `QCM-INSA`.
- Les réponses et les notes restent en base ; sauvegarder `db.sqlite3` si
  nécessaire, puis fermer le portable.
- Réactiver la mise en veille si elle avait été désactivée pour la séance.

---

## 9. Aide-mémoire

```text
1. Créer le hotspot (Paramètres Windows / Partage macOS / nmcli Linux).
   Linux : relever d'abord l'interface avec `nmcli device status` (wlo1,
   wlp2s0…), puis `nmcli device wifi hotspot ifname <interface> ...`.
2. Relever l'adresse IPv4 du portable sur le hotspot.
3. QCM_LAN_HOST=<adresse>:8000 python manage.py runserver 0.0.0.0:8000
4. Ouvrir la page initiale de la séance et projeter le QR code.
5. Tester avec un téléphone, puis distribuer.
6. Après la séance : Ctrl+C sur le serveur, arrêter le hotspot, retirer la
   règle de pare-feu si elle n'est plus utile, reconnecter le Wi-Fi habituel
   et demander aux élèves de revenir sur leur réseau.
```
