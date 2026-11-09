"""Adresses acceptées pour l'accès depuis un téléphone sur le Wi-Fi local."""

from config.settings import _hotes_locaux


def test_hotes_locaux_contient_localhost_et_loopback():
    hotes = _hotes_locaux()

    assert "localhost" in hotes
    assert "127.0.0.1" in hotes
