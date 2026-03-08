from django.db import transaction
from django.utils.text import slugify

from .models import Category, Product


def generate_unique_slug(model_class, value: str, slug_field: str = "slug") -> str:
    base_slug = slugify(value)
    slug = base_slug
    counter = 1

    while model_class.objects.filter(**{slug_field: slug}).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


@transaction.atomic
def create_category(**validated_data) -> Category:
    if not validated_data.get("slug"):
        validated_data["slug"] = generate_unique_slug(Category, validated_data["name"])

    return Category.objects.create(**validated_data)


@transaction.atomic
def update_category(*, instance: Category, **validated_data) -> Category:
    for attr, value in validated_data.items():
        setattr(instance, attr, value)

    if not instance.slug:
        instance.slug = generate_unique_slug(Category, instance.name)

    instance.save()
    return instance


@transaction.atomic
def create_product(**validated_data) -> Product:
    if not validated_data.get("slug"):
        validated_data["slug"] = generate_unique_slug(Product, validated_data["title"])

    return Product.objects.create(**validated_data)


@transaction.atomic
def update_product(*, instance: Product, **validated_data) -> Product:
    for attr, value in validated_data.items():
        setattr(instance, attr, value)

    if not instance.slug:
        instance.slug = generate_unique_slug(Product, instance.title)

    instance.save()
    return instance