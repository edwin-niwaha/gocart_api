# apps/notifications/tasks.py
from __future__ import annotations

import logging

from celery import shared_task

from apps.orders.models import Order
from .push import send_push_to_user

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_order_push_notification_task(self, order_id: int) -> None:
    order = (
        Order.objects.select_related("user", "address")
        .prefetch_related("items", "items__product", "items__variant")
        .get(id=order_id)
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