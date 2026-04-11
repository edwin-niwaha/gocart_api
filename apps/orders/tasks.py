from __future__ import annotations

import logging
from typing import Callable

from celery import shared_task

from apps.notifications.push import send_push_to_user
from .emails import (
    send_admin_order_status_email,
    send_customer_order_status_email,
    send_new_order_admin_email,
    send_order_confirmation_email,
)
from .models import Order

logger = logging.getLogger(__name__)


def _get_order(order_id: int) -> Order:
    return (
        Order.objects.select_related("user", "address")
        .prefetch_related("items", "items__product", "items__variant")
        .get(id=order_id)
    )


def _run_email_task(
    *,
    order_id: int,
    action_label: str,
    sender: Callable[[Order], None],
    recipient_getter: Callable[[Order], str | None] | None = None,
) -> None:
    try:
        order = _get_order(order_id)
        recipient = recipient_getter(order) if recipient_getter else None

        if recipient:
            logger.info("Sending %s for order_id=%s to=%s", action_label, order_id, recipient)
        else:
            logger.info("Sending %s for order_id=%s", action_label, order_id)

        sender(order)

        logger.info("Sent %s for order_id=%s", action_label, order_id)
    except Exception:
        logger.exception("Failed %s for order_id=%s", action_label, order_id)
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_order_confirmation_email_task(self, order_id: int) -> None:
    _run_email_task(
        order_id=order_id,
        action_label="order confirmation email",
        sender=send_order_confirmation_email,
        recipient_getter=lambda order: getattr(order.user, "email", None),
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_new_order_admin_email_task(self, order_id: int) -> None:
    _run_email_task(
        order_id=order_id,
        action_label="admin new-order email",
        sender=send_new_order_admin_email,
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_customer_order_status_email_task(self, order_id: int) -> None:
    _run_email_task(
        order_id=order_id,
        action_label="customer order status email",
        sender=send_customer_order_status_email,
        recipient_getter=lambda order: getattr(order.user, "email", None),
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_admin_order_status_email_task(self, order_id: int) -> None:
    _run_email_task(
        order_id=order_id,
        action_label="admin order status email",
        sender=send_admin_order_status_email,
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_order_push_notification_task(self, order_id: int) -> None:
    try:
        order = _get_order(order_id)

        logger.info(
            "Sending order push notification for order_id=%s user_id=%s",
            order_id,
            order.user_id,
        )

        send_push_to_user(
            user=order.user,
            title="Order updated",
            body=f"Your order {order.slug} is now {order.get_status_display()}",
            data={
                "type": "order_status",
                "order_id": str(order.id),
                "order_slug": order.slug,
                "status": order.status,
            },
        )

        logger.info("Sent order push notification for order_id=%s", order_id)
    except Exception:
        logger.exception("Failed order push notification for order_id=%s", order_id)
        raise