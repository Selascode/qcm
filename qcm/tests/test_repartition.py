"""Rotation par blocs : génération des étapes virtuelles (V2)."""

from qcm.services.repartition import decouper_en_paquets, generer_etapes


def test_dix_questions_donnent_dix_etapes():
    questions = [f"Q{index}" for index in range(1, 11)]

    etapes = generer_etapes(questions, max_par_etape=4)

    assert len(etapes) == 10
    assert [len(etape.paquet) for etape in etapes] == [4] * 8 + [2, 2]
    assert etapes[0].paquet == ("Q1", "Q2", "Q3", "Q4")
    assert etapes[0].index_dans_paquet == 0
    assert etapes[3].paquet == ("Q1", "Q2", "Q3", "Q4")
    assert etapes[4].paquet == ("Q5", "Q6", "Q7", "Q8")
    assert etapes[4].numero_paquet == 2
    assert etapes[8].paquet == ("Q9", "Q10")
    assert etapes[9].index_dans_paquet == 1


def test_cinq_questions_donnent_cinq_etapes():
    questions = [f"Q{index}" for index in range(1, 6)]

    etapes = generer_etapes(questions, max_par_etape=4)

    assert len(etapes) == 5
    assert [etape.numero for etape in etapes] == [1, 2, 3, 4, 5]
    assert etapes[4].paquet == ("Q5",)
    assert etapes[4].numero_paquet == 2


def test_decoupage_et_cas_vides():
    assert generer_etapes([], max_par_etape=4) == []
    assert decouper_en_paquets([], max_par_etape=4) == []
    assert decouper_en_paquets(["A", "B", "C"], max_par_etape=2) == [
        ["A", "B"],
        ["C"],
    ]
