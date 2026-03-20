from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Order
from .notifications import queue_order_status_notifications


@receiver(pre_save, sender=Order)
def capture_old_order_status(sender, instance: Order, **kwargs):
    """
    Store the previous status on the instance before save so post_save
    can compare old vs new safely.
    """
    if not instance.pk:
        instance._old_status = None
        return

    try:
        previous = Order.objects.only("status").get(pk=instance.pk)
        instance._old_status = previous.status
    except Order.DoesNotExist:
        instance._old_status = None


@receiver(post_save, sender=Order)
def send_order_status_notifications_on_change(
    sender,
    instance: Order,
    created: bool,
    **kwargs,
):
    """
    Send status notifications only when an existing order changes status.
    Do not send on initial creation because checkout already sends the
    order confirmation email.
    """
    if created:
        return

    old_status = getattr(instance, "_old_status", None)
    new_status = instance.status

    if not old_status or old_status == new_status:
        return

    queue_order_status_notifications(instance.id, old_status, new_status)