from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Order
from .notifications import queue_order_status_notifications
from apps.notifications.services import send_order_notification


@receiver(pre_save, sender=Order)
def capture_old_order_status(sender, instance: Order, **kwargs):
    """
    Store the previous status on the instance before save so post_save
    can compare old vs new safely.
    """
    if not instance.pk:
        instance._old_status = None  # type: ignore
        return

    try:
        previous = Order.objects.only("status").get(pk=instance.pk)
        instance._old_status = previous.status  # type: ignore
    except Order.DoesNotExist:
        instance._old_status = None  # type: ignore


@receiver(post_save, sender=Order)
def send_order_status_notifications_on_change(sender, instance: Order, created: bool, **kwargs):
    if created:
        return

    old_status = getattr(instance, "_old_status", None)
    new_status = instance.status

    if not old_status or old_status == new_status:
        return

    queue_order_status_notifications(instance.id, old_status, new_status)

    if instance.user_id:
        send_order_notification(
            user=instance.user,
            order=instance,
            title="Order status updated",
            message=f"Your order {instance.slug} is now {instance.get_status_display()}",
        )


@receiver(post_save, sender=Order)
def handle_stock_on_status_change(sender, instance: Order, created: bool, **kwargs):
    if created:
        return

    old_status = getattr(instance, "_old_status", None)
    new_status = instance.status

    if not old_status or old_status == new_status:
        return

    if new_status == Order.Status.CANCELLED:
        for item in instance.items.select_related("variant"):  # type: ignore
            variant = item.variant
            variant.stock_quantity += item.quantity
            variant.save(update_fields=["stock_quantity"])
