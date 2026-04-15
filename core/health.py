from __future__ import annotations

from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse


def live(request):
    return JsonResponse({"status": "ok", "environment": settings.ENVIRONMENT})


def ready(request):
    checks = {"database": False, "redis_configured": bool(getattr(settings, "CELERY_BROKER_URL", ""))}
    status_code = 200

    try:
        connections["default"].cursor()
        checks["database"] = True
    except OperationalError:
        status_code = 503

    return JsonResponse(
        {
            "status": "ok" if status_code == 200 else "degraded",
            "checks": checks,
            "environment": settings.ENVIRONMENT,
        },
        status=status_code,
    )
