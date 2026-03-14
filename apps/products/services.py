from django.db import transaction
from django.utils.text import slugify

from .models import Category, Product, ProductVariant


def generate_unique_slug(model_class, value: str, slug_field: str = "slug") -> str:
    base_slug = slugify(value)
    slug = base_slug
    counter = 1

    while model_class.objects.filter(**{slug_field: slug}).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def generate_unique_sku(product_title: str, variant_name: str) -> str:
    base = slugify(f"{product_title}-{variant_name}").replace("-", "").upper()[:24]
    sku = base or "SKU"
    counter = 1

    while ProductVariant.objects.filter(sku=sku).exists():
        sku = f"{base}{counter}"
        counter += 1

    return sku


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
    variants_data = validated_data.pop("variants", [])

    if not validated_data.get("slug"):
        validated_data["slug"] = generate_unique_slug(Product, validated_data["title"])

    product = Product.objects.create(**validated_data)

    for item in variants_data:
        sku = item.get("sku") or generate_unique_sku(product.title, item["name"])
        ProductVariant.objects.create(
            product=product,
            name=item["name"],
            sku=sku,
            price=item["price"],
            stock_quantity=item.get("stock_quantity", 0),
            max_quantity_per_order=item.get("max_quantity_per_order"),
            is_active=item.get("is_active", True),
            sort_order=item.get("sort_order", 0),
        )

    return product


@transaction.atomic
def update_product(*, instance: Product, **validated_data) -> Product:
    variants_data = validated_data.pop("variants", None)

    for attr, value in validated_data.items():
        setattr(instance, attr, value)

    if not instance.slug:
        instance.slug = generate_unique_slug(Product, instance.title)

    instance.save()

    if variants_data is not None:
        existing_ids = []

        for item in variants_data:
            variant_id = item.get("id")
            sku = item.get("sku") or generate_unique_sku(instance.title, item["name"])

            if variant_id:
                variant = instance.variants.get(id=variant_id) # type: ignore
                variant.name = item["name"]
                variant.sku = sku
                variant.price = item["price"]
                variant.stock_quantity = item.get("stock_quantity", 0)
                variant.max_quantity_per_order = item.get("max_quantity_per_order")
                variant.is_active = item.get("is_active", True)
                variant.sort_order = item.get("sort_order", 0)
                variant.save()
                existing_ids.append(variant.id)
            else:
                variant = ProductVariant.objects.create(
                    product=instance,
                    name=item["name"],
                    sku=sku,
                    price=item["price"],
                    stock_quantity=item.get("stock_quantity", 0),
                    max_quantity_per_order=item.get("max_quantity_per_order"),
                    is_active=item.get("is_active", True),
                    sort_order=item.get("sort_order", 0),
                )
                existing_ids.append(variant.id) # type: ignore

        instance.variants.exclude(id__in=existing_ids).delete() # type: ignore

    return instance