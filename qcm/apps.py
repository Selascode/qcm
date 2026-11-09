"""Configuration de l'application et activation de SQLite en mode WAL."""

from django.apps import AppConfig
from django.db.backends.signals import connection_created


def activer_wal(sender, connection, **kwargs) -> None:
    """Active WAL pour SQLite (dev/démo) sans SQL brut applicatif."""
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")


class QcmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "qcm"
    verbose_name = "QCM en direct"

    def ready(self) -> None:
        connection_created.connect(
            activer_wal,
            dispatch_uid="qcm.activer_wal",
        )
