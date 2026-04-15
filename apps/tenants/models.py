from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class Tenant(TimeStampedModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    support_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=10, default="UGX")
    default_country = models.CharField(max_length=100, blank=True, default="Uganda")
    timezone = models.CharField(max_length=64, default="Africa/Kampala")
    is_default = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug", "is_active"]),
            models.Index(fields=["is_default", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            Tenant.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)


class TenantBranding(TimeStampedModel):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="branding")
    app_name = models.CharField(max_length=255, blank=True)
    logo_url = models.URLField(blank=True)
    primary_color = models.CharField(max_length=20, blank=True)
    secondary_color = models.CharField(max_length=20, blank=True)
    accent_color = models.CharField(max_length=20, blank=True)
    splash_image_url = models.URLField(blank=True)
    hero_title = models.CharField(max_length=255, blank=True)
    hero_subtitle = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Tenant branding"
        verbose_name_plural = "Tenant branding"

    def __str__(self) -> str:
        return f"Branding: {self.tenant.name}"


class TenantSettings(TimeStampedModel):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="settings")
    order_notifications_enabled = models.BooleanField(default=True)
    reviews_enabled = models.BooleanField(default=True)
    coupons_enabled = models.BooleanField(default=True)
    delivery_enabled = models.BooleanField(default=True)
    wishlist_enabled = models.BooleanField(default=True)
    support_chat_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    terms_url = models.URLField(blank=True)
    privacy_url = models.URLField(blank=True)
    maintenance_mode = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Tenant settings"
        verbose_name_plural = "Tenant settings"

    def __str__(self) -> str:
        return f"Settings: {self.tenant.name}"


class TenantFeatureFlag(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="feature_flags")
    key = models.SlugField(max_length=100)
    enabled = models.BooleanField(default=False)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("tenant", "key")
        indexes = [models.Index(fields=["tenant", "enabled"])]
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.tenant.slug}:{self.key}={'on' if self.enabled else 'off'}"


class TenantMembership(TimeStampedModel):
    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super admin"
        TENANT_OWNER = "tenant_owner", "Tenant owner"
        TENANT_ADMIN = "tenant_admin", "Tenant admin"
        MANAGER = "manager", "Manager"
        STAFF = "staff", "Staff"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_memberships")
    role = models.CharField(max_length=30, choices=Role.choices)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        unique_together = ("tenant", "user")
        indexes = [
            models.Index(fields=["tenant", "role", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} @ {self.tenant.slug} ({self.role})"
