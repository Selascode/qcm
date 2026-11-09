#!/usr/bin/env python
"""Point d'entrée Django du projet QCM en direct."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - dépend de l'environnement
        raise ImportError(
            "Django est introuvable. Activez l'environnement virtuel et "
            "installez requirements.txt."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
