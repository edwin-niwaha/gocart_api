from __future__ import annotations

import logging

from celery import shared_task

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


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_order_confirmation_email_task(self, order_id: int) -> None:
    try:
        order = _get_order(order_id)
        logger.info(
            "Sending order confirmation email for order_id=%s to=%s",
            order_id,
            getattr(order.user, "email", None),
        )
        send_order_confirmation_email(order)
        logger.info("Sent order confirmation email for order_id=%s", order_id)
    except Exception:
        logger.exception("Failed order confirmation email for order_id=%s", order_id)
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_new_order_admin_email_task(self, order_id: int) -> None:
    try:
        order = _get_order(order_id)
        logger.info("Sending admin new-order email for order_id=%s", order_id)
        send_new_order_admin_email(order)
        logger.info("Sent admin new-order email for order_id=%s", order_id)
    except Exception:
        logger.exception("Failed admin new-order email for order_id=%s", order_id)
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_customer_order_status_email_task(self, order_id: int) -> None:
    try:
        order = _get_order(order_id)
        logger.info(
            "Sending customer order status email for order_id=%s to=%s",
            order_id,
            getattr(order.user, "email", None),
        )
        send_customer_order_status_email(order)
        logger.info("Sent customer order status email for order_id=%s", order_id)
    except Exception:
        logger.exception("Failed customer order status email for order_id=%s", order_id)
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_admin_order_status_email_task(self, order_id: int) -> None:
    try:
        order = _get_order(order_id)
        logger.info("Sending admin order status email for order_id=%s", order_id)
        send_admin_order_status_email(order)
        logger.info("Sent admin order status email for order_id=%s", order_id)
    except Exception:
        logger.exception("Failed admin order status email for order_id=%s", order_id)
        raise