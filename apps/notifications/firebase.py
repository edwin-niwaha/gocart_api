from __future__ import annotations

import logging
from pathlib import Path

import firebase_admin
from firebase_admin import credentials
from django.conf import settings

logger = logging.getLogger(__name__)


def initialize_firebase() -> bool:
    if not getattr(settings, "ENABLE_FIREBASE", False):
        logger.info("Firebase initialization skipped because ENABLE_FIREBASE is disabled.")
        return False

    if firebase_admin._apps:
        return True

    path = Path(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    if not path.exists():
        logger.warning("Firebase service account file not found: %s", path)
        return False
    if path.stat().st_size == 0:
        logger.warning("Firebase service account file is empty: %s", path)
        return False

    cred = credentials.Certificate(str(path))
    firebase_admin.initialize_app(cred)
    return True
