"""Accessibilité : symboles distincts et contraste WCAG AA de la palette.

La palette compte quatre couleurs (au plus quatre questions par étape) : les
quatre symboles ● ▲ ■ ◆ sont donc utilisés. Le ★ de la spécification n'a pas de
slot tant que le modèle reste plafonné à quatre questions par étape ; l'ajouter
créerait une couleur sans question correspondante au tableau.
"""

from qcm.couleurs import COULEURS


def _canal(valeur: int) -> float:
    composante = valeur / 255
    if composante <= 0.03928:
        return composante / 12.92
    return ((composante + 0.055) / 1.055) ** 2.4


def _luminance(couleur_hex: str) -> float:
    couleur_hex = couleur_hex.lstrip("#")
    rouge, vert, bleu = (
        int(couleur_hex[index : index + 2], 16) for index in (0, 2, 4)
    )
    return (
        0.2126 * _canal(rouge)
        + 0.7152 * _canal(vert)
        + 0.0722 * _canal(bleu)
    )


def _contraste(premier: str, second: str) -> float:
    clair = max(_luminance(premier), _luminance(second))
    sombre = min(_luminance(premier), _luminance(second))
    return (clair + 0.05) / (sombre + 0.05)


def test_palette_respecte_le_contraste_wcag_aa():
    for couleur in COULEURS.values():
        ratio = _contraste(couleur["hex"], couleur["couleur_texte"])
        assert ratio >= 4.5, (
            f"{couleur['nom']} : contraste {ratio:.2f} < 4.5"
        )


def test_symboles_distincts_et_presents():
    symboles = [couleur["symbole"] for couleur in COULEURS.values()]

    assert len(set(symboles)) == len(symboles)
    assert set(symboles) == {"●", "▲", "■", "◆"}
