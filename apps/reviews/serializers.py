from rest_framework import serializers

from apps.users.serializers import UserSerializer
from .models import ProductRating, Review


class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.ReadOnlyField(source="user.id")
    product_title = serializers.CharField(source="product.title", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "user",
            "user_id",
            "product",
            "product_title",
            "product_slug",
            "rating",
            "comment",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "user",
            "user_id",
            "product_title",
            "product_slug",
            "created_at",
            "updated_at",
        )

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        product = attrs.get("product") or getattr(self.instance, "product", None)

        if not request or not request.user or request.user.is_anonymous:
            return attrs

        if self.instance is None and product:
            already_exists = Review.objects.filter(
                user=request.user,
                product=product,
            ).exists()
            if already_exists:
                raise serializers.ValidationError(
                    {"detail": "You have already reviewed this product."}
                )

        return attrs


class ProductRatingSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="product.title", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)

    class Meta:
        model = ProductRating
        fields = (
            "id",
            "product",
            "product_title",
            "product_slug",
            "average_rating",
            "total_reviews",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "product",
            "product_title",
            "product_slug",
            "average_rating",
            "total_reviews",
            "created_at",
            "updated_at",
        )