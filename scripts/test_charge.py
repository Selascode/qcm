"""Test de charge V4 : 100 élèves rejoignent et répondent en parallèle.

Le script utilise uniquement la bibliothèque standard (``concurrent.futures``,
``urllib``) et l'ORM Django pour préparer ou vérifier le scénario. Il vise un
serveur déjà lancé (``runserver 0.0.0.0:8000``) et mesure les temps de
connexion et de réponse, le nombre de succès et d'échecs, puis vérifie en base
qu'aucune réponse n'a été perdue.

Exemples :

    # Scénario autonome : crée un QCM, 100 élèves et une session, puis charge.
    python scripts/test_charge.py --url http://127.0.0.1:8000

    # Contre une session existante (les identifiants peuvent être fournis).
    python scripts/test_charge.py --code ABC123 --identifiants eleves.txt
"""

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DELAI_DEFAUT_S = 20


@dataclass
class ResultatClient:
    """Résultat d'un élève simulé."""

    identifiant: str
    ok: bool
    duree_connexion_s: float | None = None
    duree_reponse_s: float | None = None
    erreur: str | None = None


@dataclass
class ResultatCharge:
    """Agrégat d'une campagne de charge."""

    resultats: list[ResultatClient] = field(default_factory=list)
    duree_totale_s: float = 0.0

    @property
    def succes(self) -> int:
        return sum(1 for resultat in self.resultats if resultat.ok)

    @property
    def echecs(self) -> int:
        return len(self.resultats) - self.succes

    def _durees(self, attribut: str) -> list[float]:
        return [
            getattr(resultat, attribut)
            for resultat in self.resultats
            if resultat.ok and getattr(resultat, attribut) is not None
        ]

    @property
    def temps_moyen_connexion_s(self) -> float | None:
        durees = self._durees("duree_connexion_s")
        return statistics.fmean(durees) if durees else None

    @property
    def temps_moyen_reponse_s(self) -> float | None:
        durees = self._durees("duree_reponse_s")
        return statistics.fmean(durees) if durees else None

    @property
    def temps_min_reponse_s(self) -> float | None:
        durees = self._durees("duree_reponse_s")
        return min(durees) if durees else None

    @property
    def temps_max_reponse_s(self) -> float | None:
        durees = self._durees("duree_reponse_s")
        return max(durees) if durees else None

    def resume(self) -> str:
        def valeur(valeur_s: float | None) -> str:
            return "n/a" if valeur_s is None else f"{valeur_s:.3f} s"

        return (
            f"Clients simulés : {len(self.resultats)}\n"
            f"Réussites : {self.succes}\n"
            f"Échecs : {self.echecs}\n"
            f"Temps moyen de connexion : "
            f"{valeur(self.temps_moyen_connexion_s)}\n"
            f"Temps moyen de réponse : {valeur(self.temps_moyen_reponse_s)} "
            f"(min {valeur(self.temps_min_reponse_s)}, "
            f"max {valeur(self.temps_max_reponse_s)})\n"
            f"Durée totale : {self.duree_totale_s:.3f} s"
        )


def _requete(url, corps=None, jeton=None, timeout=DELAI_DEFAUT_S):
    """Exécute une requête JSON et renvoie ``(statut, données, durée)``."""
    donnees = None
    if corps is not None:
        donnees = json.dumps(corps).encode("utf-8")
    requete = urllib.request.Request(
        url,
        data=donnees,
        method="POST" if donnees is not None else "GET",
    )
    if donnees is not None:
        requete.add_header("Content-Type", "application/json")
    if jeton is not None:
        requete.add_header("X-Jeton", jeton)
    debut = time.perf_counter()
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            corps_brut = reponse.read().decode("utf-8")
            try:
                corps_json = json.loads(corps_brut)
            except json.JSONDecodeError:
                corps_json = {"raison": "réponse non JSON"}
            return reponse.status, corps_json, time.perf_counter() - debut
    except urllib.error.HTTPError as exc:
        corps_brut = exc.read().decode("utf-8", errors="replace")
        try:
            corps_json = json.loads(corps_brut)
        except json.JSONDecodeError:
            corps_json = {}
        return exc.code, corps_json, time.perf_counter() - debut
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, {"raison": str(exc)}, time.perf_counter() - debut


def _simuler_eleve(url, code, identifiant, decalage_s, timeout):
    """Connexion, lecture de l'état et réponse d'un élève simulé."""
    if decalage_s:
        time.sleep(decalage_s)

    corps = {"code": code}
    if identifiant is not None:
        corps["code_etudiant"] = identifiant
    statut, donnees, duree_connexion = _requete(
        f"{url}/api/rejoindre/", corps, timeout=timeout
    )
    if statut != 200 or not donnees.get("ok"):
        return ResultatClient(
            identifiant=identifiant or "anonyme",
            ok=False,
            duree_connexion_s=duree_connexion,
            erreur=f"rejoindre HTTP {statut} : {donnees.get('raison', '')}",
        )

    jeton = donnees.get("jeton")
    statut, etat, _ = _requete(f"{url}/api/etat/", jeton=jeton, timeout=timeout)
    lettres = etat.get("lettres") or []
    question_uid = etat.get("question_uid")
    if statut != 200 or not question_uid or not lettres:
        return ResultatClient(
            identifiant=identifiant or "anonyme",
            ok=False,
            duree_connexion_s=duree_connexion,
            erreur=f"etat HTTP {statut} : {etat.get('raison', 'sans question')}",
        )

    statut, reponse, duree_reponse = _requete(
        f"{url}/api/repondre/",
        {
            "id_client": str(uuid.uuid4()),
            "question_uid": question_uid,
            "choix": [lettres[0]],
        },
        jeton=jeton,
        timeout=timeout,
    )
    ok = statut == 200 and reponse.get("ok") is True
    return ResultatClient(
        identifiant=identifiant or "anonyme",
        ok=ok,
        duree_connexion_s=duree_connexion,
        duree_reponse_s=duree_reponse,
        erreur=None
        if ok
        else f"repondre HTTP {statut} : {reponse.get('raison', '')}",
    )


def executer_charge(
    url,
    code,
    identifiants=None,
    nb_clients=100,
    timeout=DELAI_DEFAUT_S,
    decalage_s=0.02,
):
    """Simule ``nb_clients`` élèves simultanés contre ``url``.

    ``identifiants`` est la liste des codes élèves d'une séance avec groupe ;
    ``None`` simule une séance libre (connexions anonymes). Les connexions
    sont étalées de ``decalage_s`` par client pour ne pas dépasser la file
    d'attente du serveur de développement (10 places par défaut), mais toutes
    les requêtes se chevauchent : les réponses arrivent en parallèle.
    """
    if nb_clients < 1:
        raise ValueError("nb_clients doit être supérieur ou égal à 1.")
    if identifiants is not None and len(identifiants) != nb_clients:
        raise ValueError(
            "La liste d'identifiants doit contenir exactement nb_clients."
        )
    if decalage_s < 0:
        raise ValueError("decalage_s ne peut pas être négatif.")
    base = url.rstrip("/")
    debut = time.perf_counter()
    with ThreadPoolExecutor(max_workers=nb_clients) as executeur:
        futures = [
            executeur.submit(
                _simuler_eleve,
                base,
                code,
                None if identifiants is None else identifiants[index],
                index * decalage_s,
                timeout,
            )
            for index in range(nb_clients)
        ]
        resultats = [future.result() for future in futures]
    return ResultatCharge(
        resultats=resultats,
        duree_totale_s=time.perf_counter() - debut,
    )


def _configurer_django():
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


def _donnees_quiz(duree_s):
    return {
        "titre": "Charge V4",
        "questions": [
            {
                "uid": "CHARGE1",
                "duree_s": duree_s,
                "enonce": "Question de charge : quelle lettre ?",
                "type": "unique",
                "choix": [
                    {"lettre": "A", "texte": "A", "correct": True},
                    {"lettre": "B", "texte": "B", "correct": False},
                    {"lettre": "C", "texte": "C", "correct": False},
                    {"lettre": "D", "texte": "D", "correct": False},
                ],
            }
        ],
    }


def creer_scenario(nb_eleves, duree_s):
    """Crée un professeur, un groupe, ``nb_eleves`` élèves et une session."""
    from django.contrib.auth import get_user_model

    from qcm.import_questions import importer_quiz
    from qcm.models import Groupe, Quiz, Session, Student
    from qcm.services import demarrer_session

    utilisateur = get_user_model()
    proprietaire = utilisateur.objects.filter(username="prof-charge").first()
    if proprietaire is None:
        proprietaire = utilisateur.objects.create_user(
            username="prof-charge", password=None
        )

    groupe, _ = Groupe.objects.get_or_create(
        nom="Charge 100", defaults={"proprietaire": proprietaire}
    )
    eleves = list(groupe.etudiants.order_by("id")[:nb_eleves])
    for index in range(len(eleves), nb_eleves):
        eleves.append(
            Student.objects.create(
                nom=f"Charge{index:03d}",
                prenom="Élève",
                groupe=groupe,
            )
        )

    quiz = Quiz.objects.filter(
        proprietaire=proprietaire, titre="Charge V4"
    ).first()
    if quiz is None:
        quiz = importer_quiz(_donnees_quiz(duree_s), proprietaire)

    session = Session.objects.create(quiz=quiz, groupe=groupe)
    session = demarrer_session(session)
    return session, [eleve.code_etudiant for eleve in eleves]


def _lire_identifiants(chemin):
    return [
        ligne.strip()
        for ligne in Path(chemin).read_text(encoding="utf-8").splitlines()
        if ligne.strip()
    ]


def main(argv=None):
    parseur = argparse.ArgumentParser(
        description="Test de charge à 100 clients pour l'application QCM."
    )
    parseur.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="URL de base du serveur (défaut : http://127.0.0.1:8000).",
    )
    parseur.add_argument(
        "--code",
        help="Code d'une session existante ; sans ce code, un scénario est créé.",
    )
    parseur.add_argument(
        "--identifiants",
        help="Fichier texte d'identifiants élèves, un par ligne.",
    )
    parseur.add_argument(
        "--eleves", type=int, default=100, help="Nombre de clients (défaut : 100)."
    )
    parseur.add_argument(
        "--duree", type=int, default=300, help="Durée de l'étape (défaut : 300 s)."
    )
    parseur.add_argument(
        "--timeout",
        type=float,
        default=DELAI_DEFAUT_S,
        help="Délai maximal par requête en secondes.",
    )
    parseur.add_argument(
        "--decalage",
        type=float,
        default=0.02,
        help=(
            "Décalage entre deux connexions, en secondes (défaut : 0,02 s ; "
            "évite de saturer la file d'attente du serveur de développement)."
        ),
    )
    options = parseur.parse_args(argv)

    _configurer_django()
    from qcm.models import Answer, Session
    from qcm.services import demarrer_session, reprendre

    if options.code:
        session = (
            Session.objects.select_related("quiz", "groupe")
            .filter(code_session=options.code.strip().upper())
            .first()
        )
        if session is None:
            print(f"Session inconnue : {options.code}", file=sys.stderr)
            return 2
        if options.identifiants:
            identifiants = _lire_identifiants(options.identifiants)
        elif session.groupe_id:
            identifiants = list(
                session.groupe.etudiants.order_by("id").values_list(
                    "code_etudiant", flat=True
                )
            )[: options.eleves]
        else:
            identifiants = None
        if identifiants is not None and len(identifiants) < options.eleves:
            print(
                f"Seulement {len(identifiants)} identifiants pour "
                f"{options.eleves} clients.",
                file=sys.stderr,
            )
            return 2
        if session.statut == Session.STATUT_ATTENTE:
            session = demarrer_session(session)
        elif session.statut == Session.STATUT_PAUSE:
            session = reprendre(session)
        elif session.statut != Session.STATUT_EN_COURS:
            print("La session est terminée : choisissez une autre séance.", file=sys.stderr)
            return 2
    else:
        session, identifiants = creer_scenario(options.eleves, options.duree)
        print(
            f"Scénario créé : session {session.code_session}, "
            f"{len(identifiants)} élèves."
        )

    if identifiants is None:
        identifiants_charge = None
    else:
        identifiants_charge = list(identifiants[: options.eleves])
    avant = Answer.objects.filter(session=session).count()
    print(
        f"Charge : {options.eleves} clients sur {options.url} "
        f"(session {session.code_session})…"
    )
    resultat = executer_charge(
        options.url,
        session.code_session,
        identifiants_charge,
        nb_clients=options.eleves,
        timeout=options.timeout,
        decalage_s=options.decalage,
    )
    print(resultat.resume())

    apres = Answer.objects.filter(session=session).count()
    gagnees = apres - avant
    print(f"Réponses en base : {gagnees}/{resultat.succes}")
    for resultat_client in resultat.resultats:
        if not resultat_client.ok:
            print(
                f"  Échec {resultat_client.identifiant} : "
                f"{resultat_client.erreur}",
                file=sys.stderr,
            )
    if resultat.echecs or gagnees != resultat.succes:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
