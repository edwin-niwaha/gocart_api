# apps/notifications/push.py
from __future__ import annotations

import logging
from typing import Iterable

from firebase_admin import messaging

from .models import DeviceToken

logger = logging.getLogger(__name__)


def chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(values), size):
        yield values[i:i + size]


def send_push_to_user(*, user, title: str, body: str, data: dict[str, str] | None = None) -> None:
    tokens = list(
        DeviceToken.objects.filter(user=user, is_active=True)
        .values_list("token", flat=True)
    )

    if not tokens:
        logger.info("No active push tokens for user_id=%s", user.id)
        return

    for token_batch in chunked(tokens, 500):
        message = messaging.MulticastMessage(
            tokens=token_batch,
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            android=messaging.AndroidConfig(priority="high"),
        )

        response = messaging.send_each_for_multicast(message)

        for index, result in enumerate(response.responses):
            if result.success:
                continue

            failed_token = token_batch[index]
            logger.warning(
                "FCM failed for user_id=%s token=%s error=%s",
                user.id,
                failed_token,
                result.exception,
            )

            DeviceToken.objects.filter(token=failed_token).update(is_active=False)