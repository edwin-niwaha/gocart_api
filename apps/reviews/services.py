from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count

from .models import ProductRating, Review


@transaction.atomic
def update_product_rating(product):
    aggregates = Review.objects.filter(product=product).aggregate(
        average=Avg("rating"),
        total=Count("id"),
    )

    average = aggregates["average"] or 0
    total = aggregates["total"] or 0

    rating_obj, _ = ProductRating.objects.get_or_create(product=product)
    rating_obj.average_rating = (
        Decimal(str(round(average, 2))) if total else Decimal("0.00")
    )
    rating_obj.total_reviews = total
    rating_obj.save(update_fields=["average_rating", "total_reviews", "updated_at"])

    return rating_obj


@transaction.atomic
def create_review(*, user, **validated_data) -> Review:
    review = Review.objects.create(user=user, **validated_data)
    update_product_rating(review.product)
    return review


@transaction.atomic
def update_review(*, instance: Review, **validated_data) -> Review:
    old_product = instance.product

    for attr, value in validated_data.items():
        setattr(instance, attr, value)

    instance.save()
    update_product_rating(instance.product)

    if old_product != instance.product:
        update_product_rating(old_product)

    return instance


@transaction.atomic
def delete_review(*, instance: Review) -> None:
    product = instance.product
    instance.delete()
    update_product_rating(product)