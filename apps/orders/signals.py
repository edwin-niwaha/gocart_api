from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import OrderItem


@receiver(post_save, sender=OrderItem)
def update_order_total_on_save(sender, instance, **kwargs):
    instance.order.recalculate_total_price()


@receiver(post_delete, sender=OrderItem)
def update_order_total_on_delete(sender, instance, **kwargs):
    instance.order.recalculate_total_price()