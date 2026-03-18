from django.db import transaction

from .models import CustomerAddress


@transaction.atomic
def create_address(*, user, **validated_data) -> CustomerAddress:
    is_default = validated_data.get("is_default", False)

    if is_default:
        CustomerAddress.objects.filter(user=user, is_default=True).update(is_default=False)

    elif not CustomerAddress.objects.filter(user=user).exists():
        validated_data["is_default"] = True

    address = CustomerAddress.objects.create(user=user, **validated_data)
    return address


@transaction.atomic
def update_address(*, instance: CustomerAddress, **validated_data) -> CustomerAddress:
    is_default = validated_data.get("is_default")

    if is_default is True:
        CustomerAddress.objects.filter(user=instance.user).exclude(pk=instance.pk).update(is_default=False)

    for attr, value in validated_data.items():
        setattr(instance, attr, value)

    instance.save()
    return instance


@transaction.atomic
def delete_address(*, instance: CustomerAddress) -> None:
    user = instance.user
    was_default = instance.is_default
    instance.delete()

    if was_default:
        next_address = (
            CustomerAddress.objects.filter(user=user)
            .order_by("-created_at")
            .first()
        )
        if next_address:
            next_address.is_default = True
            next_address.save(update_fields=["is_default", "updated_at"])