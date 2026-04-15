from django.db import transaction
from django.utils.text import slugify

from apps.tenants.models import Tenant
from .models import Category, Product, ProductVariant


def generate_unique_slug(
    model_class,
    value: str,
    *,
    tenant: Tenant,
    slug_field: str = "slug",
    exclude_id: int | None = None,
) -> str:
    base_slug = slugify(value).strip("-") or "item"
    slug = base_slug
    counter = 1

    queryset = model_class.objects.filter(tenant=tenant)
    if exclude_id is not None:
        queryset = queryset.exclude(id=exclude_id)

    while queryset.filter(**{slug_field: slug}).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def generate_unique_sku(
    product_title: str,
    variant_name: str,
    *,
    tenant: Tenant,
    exclude_id: int | None = None,
) -> str:
    base = slugify(f"{product_title}-{variant_name}").replace("-", "").upper()[:24] or "SKU"
    sku = base
    counter = 1

    queryset = ProductVariant.objects.filter(tenant=tenant)
    if exclude_id is not None:
        queryset = queryset.exclude(id=exclude_id)

    while queryset.filter(sku=sku).exists():
        sku = f"{base}{counter}"
        counter += 1

    return sku


def _build_variant_defaults(product: Product, item: dict) -> dict:
    return {
        "tenant": product.tenant,
        "product": product,
        "name": item["name"].strip(),
        "sku": (item.get("sku") or "").strip() or generate_unique_sku(product.title, item["name"], tenant=product.tenant),
        "price": item["price"],
        "stock_quantity": item.get("stock_quantity", 0),
        "max_quantity_per_order": item.get("max_quantity_per_order"),
        "is_active": item.get("is_active", True),
        "sort_order": item.get("sort_order", 0),
    }


@transaction.atomic
def create_category(*, tenant: Tenant, **validated_data) -> Category:
    name = validated_data.get("name", "").strip()
    validated_data["name"] = name
    validated_data["tenant"] = tenant

    slug = (validated_data.get("slug") or "").strip()
    if not slug:
        validated_data["slug"] = generate_unique_slug(Category, name, tenant=tenant)
    else:
        validated_data["slug"] = slug

    return Category.objects.create(**validated_data)


@transaction.atomic
def update_category(*, instance: Category, **validated_data) -> Category:
    if "name" in validated_data and validated_data["name"]:
        validated_data["name"] = validated_data["name"].strip()

    if "slug" in validated_data and validated_data["slug"]:
        validated_data["slug"] = validated_data["slug"].strip()

    for attr, value in validated_data.items():
        setattr(instance, attr, value)

    if not (instance.slug or "").strip():
        instance.slug = generate_unique_slug(Category, instance.name, tenant=instance.tenant, exclude_id=instance.id)

    instance.save()
    return instance


@transaction.atomic
def create_product(*, tenant: Tenant, **validated_data) -> Product:
    variants_data = validated_data.pop("variants", [])

    title = validated_data.get("title", "").strip()
    validated_data["title"] = title
    validated_data["tenant"] = tenant

    if "description" in validated_data and validated_data["description"] is not None:
        validated_data["description"] = validated_data["description"].strip()

    slug = (validated_data.get("slug") or "").strip()
    if not slug:
        validated_data["slug"] = generate_unique_slug(Product, title, tenant=tenant)
    else:
        validated_data["slug"] = slug

    product = Product.objects.create(**validated_data)

    for item in variants_data:
        ProductVariant.objects.create(**_build_variant_defaults(product, item))

    return product


@transaction.atomic
def update_product(*, instance: Product, **validated_data) -> Product:
    variants_data = validated_data.pop("variants", None)

    if "title" in validated_data and validated_data["title"]:
        validated_data["title"] = validated_data["title"].strip()

    if "description" in validated_data and validated_data["description"] is not None:
        validated_data["description"] = validated_data["description"].strip()

    if "slug" in validated_data and validated_data["slug"]:
        validated_data["slug"] = validated_data["slug"].strip()

    for attr, value in validated_data.items():
        setattr(instance, attr, value)

    if instance.category.tenant_id != instance.tenant_id:
        instance.category = Category.objects.get(id=instance.category_id, tenant=instance.tenant)

    if not (instance.slug or "").strip():
        instance.slug = generate_unique_slug(Product, instance.title, tenant=instance.tenant, exclude_id=instance.id)

    instance.save()

    if variants_data is not None:
        kept_variant_ids: list[int] = []
        existing_variants = {variant.id: variant for variant in instance.variants.all()}

        for item in variants_data:
            variant_id = item.get("id")
            variant_name = item["name"].strip()
            variant_sku = (item.get("sku") or "").strip()

            if variant_id and variant_id in existing_variants:
                variant = existing_variants[variant_id]
                variant.name = variant_name
                variant.sku = variant_sku or generate_unique_sku(instance.title, variant_name, tenant=instance.tenant, exclude_id=variant.id)
                variant.price = item["price"]
                variant.stock_quantity = item.get("stock_quantity", 0)
                variant.max_quantity_per_order = item.get("max_quantity_per_order")
                variant.is_active = item.get("is_active", True)
                variant.sort_order = item.get("sort_order", 0)
                variant.tenant = instance.tenant
                variant.save()
                kept_variant_ids.append(variant.id)
            else:
                variant = ProductVariant.objects.create(
                    tenant=instance.tenant,
                    product=instance,
                    name=variant_name,
                    sku=variant_sku or generate_unique_sku(instance.title, variant_name, tenant=instance.tenant),
                    price=item["price"],
                    stock_quantity=item.get("stock_quantity", 0),
                    max_quantity_per_order=item.get("max_quantity_per_order"),
                    is_active=item.get("is_active", True),
                    sort_order=item.get("sort_order", 0),
                )
                kept_variant_ids.append(variant.id)

        instance.variants.exclude(id__in=kept_variant_ids).delete()

    return instance
