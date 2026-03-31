from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

if TYPE_CHECKING:
    from .models import Order

logger = logging.getLogger(__name__)


def _display_name(order: Order) -> str:
    full_name = order.user.get_full_name().strip()
    return full_name or order.user.email or "Customer"


def _common_context(order: Order) -> dict[str, Any]:
    items = order.items.select_related("product", "variant").all()
    return {
        "order": order,
        "user": order.user,
        "items": items,
        "display_name": _display_name(order),
        "shop_name": "GoCart",
        "support_email": settings.DEFAULT_FROM_EMAIL,
        "admin_email": settings.DEFAULT_FROM_EMAIL,
    }


def _send_templated_email(
    *,
    subject: str,
    to: list[str],
    text_template: str,
    html_template: str,
    context: dict[str, Any],
) -> None:
    if not to:
        logger.warning("Skipped email with empty recipient list. subject=%s", subject)
        return

    text_body = render_to_string(text_template, context)
    html_body = render_to_string(html_template, context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def send_order_confirmation_email(order: Order) -> None:
    recipient = order.user.email
    if not recipient:
        logger.warning("Order confirmation skipped: order_id=%s has no user email", order.id)
        return

    context = _common_context(order)
    subject = f"Order received: {order.slug}"

    _send_templated_email(
        subject=subject,
        to=[recipient],
        text_template="order_emails/order_confirmation.txt",
        html_template="order_emails/order_confirmation.html",
        context=context,
    )


def send_new_order_admin_email(order: Order) -> None:
    recipient = settings.DEFAULT_FROM_EMAIL
    if not recipient:
        logger.warning("Admin new-order email skipped: DEFAULT_FROM_EMAIL is empty")
        return

    context = _common_context(order)
    subject = f"New order placed: {order.slug}"

    _send_templated_email(
        subject=subject,
        to=[recipient],
        text_template="order_emails/new_order_admin.txt",
        html_template="order_emails/new_order_admin.html",
        context=context,
    )


def send_customer_order_status_email(order: Order) -> None:
    recipient = order.user.email
    if not recipient:
        logger.warning("Customer status email skipped: order_id=%s has no user email", order.id)
        return

    context = _common_context(order)
    context["status_label"] = order.get_status_display()
    subject = f"Order update: {order.slug} is now {order.get_status_display()}"

    _send_templated_email(
        subject=subject,
        to=[recipient],
        text_template="order_emails/customer_order_status.txt",
        html_template="order_emails/customer_order_status.html",
        context=context,
    )


def send_admin_order_status_email(order: Order) -> None:
    recipient = settings.DEFAULT_FROM_EMAIL
    if not recipient:
        logger.warning("Admin status email skipped: DEFAULT_FROM_EMAIL is empty")
        return

    context = _common_context(order)
    context["status_label"] = order.get_status_display()
    subject = f"Order status changed: {order.slug} is now {order.get_status_display()}"

    _send_templated_email(
        subject=subject,
        to=[recipient],
        text_template="order_emails/admin_order_status.txt",
        html_template="order_emails/admin_order_status.html",
        context=context,
    )