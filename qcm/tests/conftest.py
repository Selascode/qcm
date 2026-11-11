"""Fixtures communes aux tests."""

import pytest
from django.contrib.auth import get_user_model

from qcm.models import Groupe


@pytest.fixture
def proprietaire(db):
    return get_user_model().objects.create_user(
        username="prof",
        password="secret",
    )


@pytest.fixture
def autre_proprietaire(db):
    return get_user_model().objects.create_user(
        username="autre",
        password="secret",
    )


@pytest.fixture
def groupe(proprietaire):
    return Groupe.objects.create(nom="ISIA4", proprietaire=proprietaire)
