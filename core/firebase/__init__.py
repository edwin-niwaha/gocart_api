from django.conf import settings

if getattr(settings, "ENABLE_FIREBASE", False):
    try:
        from firebase_admin import credentials, initialize_app

        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
        initialize_app(cred)
    except Exception:
        pass