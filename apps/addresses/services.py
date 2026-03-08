from django.db import transaction

from .models import CustomerAddress


@transaction.atomic
def create_address(*, user, **validated_data) -> CustomerAddress:
    if validated_data.get("is_default", False):
        CustomerAddress.objects.filter(user=user).update(is_default=False)

    return CustomerAddress.objects.create(user=user, **validated_data)


@transaction.atomic
def update_address(*, instance: CustomerAddress, **validated_data) -> CustomerAddress:
    if validated_data.get("is_default", False):
        CustomerAddress.objects.filter(user=instance.user).exclude(pk=instance.pk).update(
            is_default=False
        )

    for attr, value in validated_data.items():
        setattr(instance, attr, value)

    instance.save()
    return instance


@transaction.atomic
def delete_address(*, instance: CustomerAddress) -> None:
    was_default = instance.is_default
    user = instance.user
    instance.delete()

    if was_default:
        next_address = CustomerAddress.objects.filter(user=user).order_by("-created_at").first()
        if next_address:
            next_address.is_default = True
            next_address.save(update_fields=["is_default", "updated_at"])