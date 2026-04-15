from django.utils import timezone

from .models import Notification


def create_notification(
    *,
    user,
    tenant,
    notification_type: str,
    title: str,
    message: str,
    data: dict | None = None,
) -> Notification:
    return Notification.objects.create(
        tenant=tenant,
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        data=data or {},
    )


def mark_notification_read(*, notification: Notification) -> Notification:
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return notification


def mark_all_notifications_read(*, user, tenant) -> int:
    now = timezone.now()
    updated = Notification.objects.filter(user=user, tenant=tenant, is_read=False).update(
        is_read=True,
        read_at=now,
        updated_at=now,
    )
    return updated


def send_order_notification(*, user, order, title: str, message: str) -> Notification:
    return create_notification(
        user=user,
        tenant=order.tenant,
        notification_type=Notification.NotificationType.ORDER,
        title=title,
        message=message,
        data={"order_slug": order.slug},
    )


def send_payment_notification(*, user, payment, title: str, message: str) -> Notification:
    return create_notification(
        user=user,
        tenant=payment.order.tenant,
        notification_type=Notification.NotificationType.PAYMENT,
        title=title,
        message=message,
        data={
            "payment_id": payment.id,
            "reference": payment.reference,
            "order_slug": payment.order.slug,
        },
    )


def send_shipping_notification(*, user, shipment, title: str, message: str) -> Notification:
    return create_notification(
        user=user,
        tenant=shipment.order.tenant,
        notification_type=Notification.NotificationType.SHIPPING,
        title=title,
        message=message,
        data={
            "shipment_id": shipment.id,
            "order_slug": shipment.order.slug,
            "tracking_number": shipment.tracking_number,
        },
    )


def send_promotion_notification(*, user, coupon, title: str, message: str) -> Notification:
    return create_notification(
        user=user,
        tenant=coupon.tenant,
        notification_type=Notification.NotificationType.PROMOTION,
        title=title,
        message=message,
        data={
            "coupon_code": coupon.code,
        },
    )
