# 0013 — Statistiques de fin d'étape et test de charge V4

## Contexte

La V4 demande d'afficher, dans le Mode Présentation, la répartition des
réponses de la classe à la fin de chaque étape, avec la bonne réponse
clairement identifiée. Or la séance avance automatiquement à `ends_at` : sans
intervention, les questions de l'étape suivante remplacent immédiatement
celles qui viennent de se terminer, et les statistiques ne seraient visibles
qu'une fraction de seconde. Le ticket demande aussi un test de charge à 100
clients simultanés et un guide de réseau local.

## Décision

### Statistiques de fin d'étape

- **Calcul serveur, affichage professeur seulement.** Le service
  `services.statistiques_etape()` compte, pour chaque question de l'étape, les
  réponses enregistrées par lettre. Le pourcentage porte sur les élèves ayant
  répondu à la question (0 % si aucune réponse) ; une question à choix
  multiple compte chaque lettre cochée, donc la somme peut dépasser 100 %.
  La bonne réponse est lue depuis `Choice.est_correct`, uniquement dans la vue
  `/tableau/<code>/presentation/` protégée par l'authentification et la
  propriété du QCM. Aucun endpoint élève ne reçoit ces données.
- **Affichage en CSS pur.** Les barres sont des `div`/`span` dont la largeur
  est un pourcentage inline ; aucune bibliothèque de graphiques n'est ajoutée.
  La ligne de la bonne réponse est bordée en vert et marquée d'un ✓.
- **Déclencheur.** Les statistiques apparaissent quand la séance est en pause
  ou quand `fin_etape_atteinte()` est vrai (`en_cours` avec
  `temps_restant_s == 0`).
- **Pause de fin d'étape.** La page de présentation programme, à partir de
  l'`ends_at` serveur, l'action de pilotage `pause_fin_etape` avec le numéro
  d'étape attendu. Le serveur vérifie l'étape, remet `reste_en_pause` à 0 et
  passe la séance en pause ; la page se recharge alors avec les statistiques.
  Le professeur avance avec **Suivant** depuis le tableau. L'action est
  idempotente si deux onglets de présentation la demandent.
- **Marge de 2 s.** `avancer_si_necessaire()` attend `MARGE_FIN_ETAPE_S` (2 s)
  après `ends_at` avant d'avancer. Cette marge évite la course entre
  l'auto-avance (déclenchée par n'importe quel polling) et la demande de pause
  de la page de présentation. Les réponses reçues après `ends_at` restent
  refusées : la marge ne concerne que l'avancement de l'étape, jamais
  l'acceptation d'une réponse.
- **Hors Mode Présentation**, l'auto-avance V1 reste le comportement par
  défaut (avec le même délai de 2 s).

### Test de charge

- **Script standard library.** `scripts/test_charge.py` utilise
  `concurrent.futures.ThreadPoolExecutor`, `urllib` et l'ORM Django. Il peut
  créer son propre scénario (professeur `prof-charge`, groupe de 100 élèves,
  QCM et session) ou cibler une session existante avec `--code` et un fichier
  d'identifiants. Il mesure les temps de connexion et de réponse, compte les
  succès/échecs et vérifie en base que les `Answer` attendues sont présentes.
- **Test automatisé.** `qcm/tests/test_charge.py` rejoue 100 clients contre le
  `live_server` de pytest-django et vérifie 100 réponses en base, sans échec.
- **Connexions étalées de 20 ms.** Le serveur de développement Django a une
  file d'attente de 10 connexions (`WSGIServer.request_queue_size`). Un burst
  TCP de 100 connexions simultanées provoque des `Connection reset by peer`
  avant même d'atteindre l'application. Le script étale donc les connexions de
  20 ms par client (2 s au total) tout en gardant les requêtes chevauchantes ;
  il ne s'agit pas de sérialiser les élèves, mais de ne pas saturer une limite
  du serveur de développement. Pour une vraie salle, un serveur WSGI de
  production est recommandé.
- **Verrou d'écriture SQLite.** Sous SQLite, 100 transactions qui lisent puis
  écrivent (connexion d'un élève, réponse, mise à jour d'activité) se heurtent
  à `database is locked` : le verrou de lecture est pris avant l'écriture et
  une autre transaction peut avoir changé la base entre-temps. Un
  `threading.RLock` applicatif sérialise ces écritures lorsque
  `connection.vendor == "sqlite"` ; il est sans effet sous PostgreSQL. Le
  verrou est réentrant car la mise à jour d'activité est appelée à l'intérieur
  de la transaction de connexion.

## Conséquences

- Le Mode Présentation change de rythme : à la fin de chaque étape, la séance
  se met en pause pour les statistiques et le professeur clique sur
  **Suivant**. C'est le comportement attendu par la fonctionnalité, mais il
  diffère de l'auto-avance historique ; le guide professeur et le README le
  documentent. Sans Mode Présentation, rien ne change, hormis les 2 s de marge
  avant l'auto-avance.
- Pendant la marge de 2 s, `temps_restant_s` vaut 0 et le statut reste
  `en_cours` ; les téléphones affichent 0 et les réponses sont refusées. La
  marge est volontairement courte.
- Le verrou SQLite est propre à un processus. Le déploiement documenté est un
  serveur local unique (`runserver` ou un seul worker) ; une installation
  multi-workers sous SQLite devrait déplacer la sérialisation au niveau du
  serveur de base ou passer à PostgreSQL. Sous PostgreSQL, le verrou n'est
  pas utilisé.
- Aucune migration ni nouvelle dépendance. Les modèles, le barème et la
  politique de polling ne changent pas.
- Les statistiques restent côté professeur : aucun énoncé, texte de choix ou
  `est_correct` supplémentaire n'est exposé aux élèves.
