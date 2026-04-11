from __future__ import annotations

from pathlib import Path

import firebase_admin
from firebase_admin import credentials
from django.conf import settings


def initialize_firebase() -> None:
    if firebase_admin._apps:
        return

    path = Path(settings.FIREBASE_SERVICE_ACCOUNT_PATH)

    if not path.exists():
        raise FileNotFoundError(
            f"Firebase service account file not found: {path}"
        )

    if path.stat().st_size == 0:
        raise ValueError(
            f"Firebase service account file is empty: {path}"
        )

    cred = credentials.Certificate(str(path))
    firebase_admin.initialize_app(cred)