"""Palette de couleurs et symboles de la V1.

Quatre couleurs, chacune doublée d'un symbole : le symbole porte l'information
même en cas de daltonisme (SPEC §4). La couleur d'une question est sa position
1..T dans le paquet affiché, pas l'identité d'un élève.
"""

COULEURS = {
    1: {
        "slot": 1,
        "nom": "Rouge",
        "symbole": "●",
        "hex": "#C62828",
        "couleur_texte": "#FFFFFF",
    },
    2: {
        "slot": 2,
        "nom": "Bleu",
        "symbole": "▲",
        "hex": "#1565C0",
        "couleur_texte": "#FFFFFF",
    },
    3: {
        "slot": 3,
        "nom": "Vert",
        "symbole": "■",
        "hex": "#2E7D32",
        "couleur_texte": "#FFFFFF",
    },
    4: {
        "slot": 4,
        "nom": "Violet",
        "symbole": "◆",
        "hex": "#6A1B9A",
        "couleur_texte": "#FFFFFF",
    },
}

NB_COULEURS = len(COULEURS)


def infos_couleur(slot: int) -> dict:
    """Retourne les informations d'affichage d'un slot de couleur."""
    return COULEURS[slot]
