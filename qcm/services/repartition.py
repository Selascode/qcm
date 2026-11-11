"""Découpage des questions en paquets et génération des étapes virtuelles.

Un paquet de T questions génère T étapes virtuelles identiques : à chaque
étape, la couleur de l'élève tourne, ce qui l'oblige à répondre à une question
différente du paquet. La sélection ordonnée vit dans ``QuizQuestion`` ; les
étapes et leurs paquets sont recalculés à la volée, sans duplication de
données.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EtapeVirtuelle:
    numero: int
    paquet: tuple
    index_dans_paquet: int
    numero_paquet: int

    @property
    def taille_paquet(self) -> int:
        return len(self.paquet)


def decouper_en_paquets(questions, max_par_etape: int = 4) -> list[list]:
    """Découpe les questions en paquets contigus de ``max_par_etape`` maximum."""
    if max_par_etape < 1:
        raise ValueError("max_par_etape doit être supérieur ou égal à 1.")
    questions = list(questions)
    return [
        questions[debut : debut + max_par_etape]
        for debut in range(0, len(questions), max_par_etape)
    ]


def generer_etapes(questions, max_par_etape: int = 4) -> list[EtapeVirtuelle]:
    """Génère T étapes virtuelles pour un paquet de T questions.

    Exemple : 10 questions (max 4) → 4 étapes Q1-Q4, 4 étapes Q5-Q8,
    2 étapes Q9-Q10, soit 10 étapes.
    """
    etapes = []
    numero = 0
    for numero_paquet, paquet in enumerate(
        decouper_en_paquets(questions, max_par_etape), start=1
    ):
        for index in range(len(paquet)):
            numero += 1
            etapes.append(
                EtapeVirtuelle(
                    numero=numero,
                    paquet=tuple(paquet),
                    index_dans_paquet=index,
                    numero_paquet=numero_paquet,
                )
            )
    return etapes
