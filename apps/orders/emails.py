from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

if TYPE_CHECKING:
    from .models import Order

logger = logging.getLogger(__name__)


SHOP_NAME = "GoCart"


@dataclass(frozen=True)
class EmailSpec:
    subject_builder: Callable[[Any], str]
    recipient_getter: Callable[[Any], str | None]
    text_template: str
    html_template: str
    skip_log_message: str


def _customer_email(order: Order) -> str | None:
    return order.contact_email or None


def _display_name(order: Order) -> str:
    return order.contact_name


def _common_context(order: Order) -> dict[str, Any]:
    return {
        "order": order,
        "user": order.user,
        "items": order.items.all(),
        "display_name": _display_name(order),
        "customer_email": _customer_email(order),
        "delivery_street_name": order.delivery_street_name,
        "delivery_city": order.delivery_city,
        "delivery_region": order.delivery_region,
        "shop_name": SHOP_NAME,
        "support_email": settings.DEFAULT_FROM_EMAIL,
        "admin_email": settings.DEFAULT_FROM_EMAIL,
    }


def _send_templated_email(
    *,
    subject: str,
    recipient: str | None,
    text_template: str,
    html_template: str,
    context: dict[str, Any],
) -> None:
    if not recipient:
        logger.warning("Skipped email: %s | subject=%s", "missing recipient", subject)
        return

    text_body = render_to_string(text_template, context)
    html_body = render_to_string(html_template, context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def _send_order_email(order: Order, spec: EmailSpec, *, extra_context: dict[str, Any] | None = None) -> None:
    context = _common_context(order)
    if extra_context:
        context.update(extra_context)

    recipient = spec.recipient_getter(order)
    if not recipient:
        logger.warning(spec.skip_log_message, order.id)
        return

    _send_templated_email(
        subject=spec.subject_builder(order),
        recipient=recipient,
        text_template=spec.text_template,
        html_template=spec.html_template,
        context=context,
    )


ORDER_EMAILS: dict[str, EmailSpec] = {
    "order_confirmation": EmailSpec(
        subject_builder=lambda order: f"Order received: {order.slug}",
        recipient_getter=_customer_email,
        text_template="order_emails/order_confirmation.txt",
        html_template="order_emails/order_confirmation.html",
        skip_log_message="Order confirmation skipped: order_id=%s has no user email",
    ),
    "new_order_admin": EmailSpec(
        subject_builder=lambda order: f"New order placed: {order.slug}",
        recipient_getter=lambda order: settings.DEFAULT_FROM_EMAIL,
        text_template="order_emails/new_order_admin.txt",
        html_template="order_emails/new_order_admin.html",
        skip_log_message="Admin new-order email skipped: order_id=%s has no admin email configured",
    ),
    "customer_order_status": EmailSpec(
        subject_builder=lambda order: f"Order update: {order.slug} is now {order.get_status_display()}",
        recipient_getter=_customer_email,
        text_template="order_emails/customer_order_status.txt",
        html_template="order_emails/customer_order_status.html",
        skip_log_message="Customer status email skipped: order_id=%s has no user email",
    ),
    "admin_order_status": EmailSpec(
        subject_builder=lambda order: f"Order status changed: {order.slug} is now {order.get_status_display()}",
        recipient_getter=lambda order: settings.DEFAULT_FROM_EMAIL,
        text_template="order_emails/admin_order_status.txt",
        html_template="order_emails/admin_order_status.html",
        skip_log_message="Admin status email skipped: order_id=%s has no admin email configured",
    ),
}


def send_order_confirmation_email(order: Order) -> None:
    _send_order_email(order, ORDER_EMAILS["order_confirmation"])


def send_new_order_admin_email(order: Order) -> None:
    _send_order_email(order, ORDER_EMAILS["new_order_admin"])


def send_customer_order_status_email(order: Order) -> None:
    _send_order_email(
        order,
        ORDER_EMAILS["customer_order_status"],
        extra_context={"status_label": order.get_status_display()},
    )


def send_admin_order_status_email(order: Order) -> None:
    _send_order_email(
        order,
        ORDER_EMAILS["admin_order_status"],
        extra_context={"status_label": order.get_status_display()},
    )
