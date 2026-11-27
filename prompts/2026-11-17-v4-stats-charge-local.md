# Prompt du 2026-11-17 — V4 : statistiques, charge et mode local

## Demande

Issue [#11](https://github.com/Selascode/qcm/issues/11), titre
« Implémentation de la V4 @Selascode-agent » :

> Implémente la V4 : Statistiques au tableau, Mode serveur local et Test de
> charge.
>
> Lis AGENTS.md, docs/SPEC.md et docs/ROADMAP.md. Propose un plan de 5-7
> lignes avant de coder. Périmètre fermé. Pas de nouvelle dépendance (sauf si
> justifiée pour le test de charge).
>
> 1. **Statistiques de classe dans le Mode Présentation (Option)** : dans
>    `/tableau/<code>/presentation/`, afficher les statistiques à la fin de
>    l'étape, uniquement quand le temps est écoulé ou après « Pause » ;
>    graphique à barres en CSS pur pour A, B, C, D ; bonne réponse marquée
>    (bordure verte ou ✓).
> 2. **Test de charge à 100 clients** : `scripts/test_charge.py` avec
>    `concurrent.futures` ou `threading`, mesure du temps moyen, succès et
>    échecs, puis test vérifiant qu'aucune `Answer` n'est perdue.
> 3. **Mode serveur local** : `docs/MODE_LOCAL.md` pour un hotspot Wi-Fi
>    Windows/macOS/Linux, lancement avec `QCM_LAN_HOST` et distribution des
>    adresses.
> 4. **Guide professeur** : mentionner les statistiques de fin d'étape et
>    renvoyer vers `docs/MODE_LOCAL.md` en cas de problème de réseau.
>
> Tests attendus : test du script de charge (100 clients, 0 perte) et test de
> l'affichage des statistiques (HTML avec les barres CSS).

## Plan publié

Plan de 6 points publié dans l'issue #11 :
[commentaire 6945443732](https://github.com/Selascode/qcm/issues/11#issuecomment-6945443732).

Point de conception signalé : en Mode Présentation, la fin de l'étape devait
mettre la séance en pause pour figer les statistiques, sinon l'auto-avance V1
rendrait l'affichage inutilisable.

## Validation humaine

Commentaire
[6945518734](https://github.com/Selascode/qcm/issues/11#issuecomment-6945518734) :
« Parfait tu peux lancer l'implémentation je valide les 2 secondes de
marges ». Le reste du plan est accepté tel quel.

## Résultat

- Service `statistiques_etape()` : comptage par choix, pourcentages sur les
  élèves ayant répondu, indication de la bonne réponse ; aucune note calculée
  ni stockée.
- Vue `/tableau/<code>/presentation/` : section de statistiques en CSS pur
  (barres, pourcentages, textes des choix, bordure verte et ✓), affichée en
  pause ou à `ends_at`, à la place des questions.
- Action `pause_fin_etape` : la page de présentation demande la pause à
  l'expiration du minuteur ; marge de 2 s dans `avancer_si_necessaire()` pour
  éviter la course avec l'auto-avance ; l'auto-avance reste le défaut hors
  Mode Présentation.
- Tests : `qcm/tests/test_statistiques.py` (service, HTML, pause, fin de
  temps), `qcm/tests/test_timer.py` (marge, pause idempotente),
  `qcm/tests/test_pilotage.py` (action API).
- Charge : `scripts/test_charge.py` (stdlib + `ThreadPoolExecutor`, scénario
  autonome ou session existante, mesures, vérification ORM) et
  `qcm/tests/test_charge.py` (`live_server`, 100 clients, 0 perte).
  Verrou d'écriture SQLite et étalement des connexions de 20 ms pour la file
  d'attente de `runserver`.
- Documentation : `docs/MODE_LOCAL.md`, mise à jour de `GUIDE_PROF.md` et
  `README.md`, ADR 0013, JOURNAL.
- Correctif hors connexion : KaTeX 0.16.11 (MIT) vendorisé dans
  `static/qcm/katex/` et chargé localement par le tableau et la présentation ;
  test `qcm/tests/test_katex.py`.
- Captures avant/après : `docs/screenshots/v4/`.

## Vérifications

- `pytest` : 268 tests passés.
- `ruff check .`, `python manage.py check`,
  `python manage.py makemigrations --check --dry-run` : OK.
- `scripts/test_charge.py` contre `runserver` : 100 réussites, 0 échec,
  100 réponses en base.
- Test navigateur : session courte en Mode Présentation, mise en pause
  automatique à la fin et affichage des statistiques.

## Décisions et enseignements

- Sans Mode Présentation, l'auto-avance V1 est conservée ; avec le mode, la
  pause de fin d'étape est nécessaire à la lecture des statistiques. La marge
  de 2 s est le compromis validé.
- SQLite ne supporte pas 100 transactions concurrentes « lecture puis
  écriture » : un `RLock` applicatif limite les `database is locked`. Il est
  limité à SQLite ; PostgreSQL n'en a pas besoin.
- La file d'attente de connexion de `runserver` (10) impose un léger
  étalement des connexions du test de charge ; ce n'est pas une limite de
  l'application elle-même.
- Aucune nouvelle dépendance. `SPEC.md`, `ARCHITECTURE.md` et `ROADMAP.md`
  ne sont pas modifiés (mise à jour humaine attendue).
