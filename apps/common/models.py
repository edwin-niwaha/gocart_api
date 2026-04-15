import uuid
from django.conf import settings
from django.db import models



class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SupportMessage(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "NEW", "New"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        RESOLVED = "RESOLVED", "Resolved"

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="support_messages", null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="support_messages", null=True, blank=True)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField(max_length=5000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="assigned_support_messages", null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        tenant_slug = self.tenant.slug if self.tenant_id else "global"
        return f"{tenant_slug} - {self.email}"


class AuditLog(TimeStampedModel):
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="audit_logs", null=True, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="audit_logs", null=True, blank=True)
    action = models.CharField(max_length=120, db_index=True)
    target_type = models.CharField(max_length=120, blank=True)
    target_id = models.CharField(max_length=120, blank=True)
    summary = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "action"]),
            models.Index(fields=["tenant", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} - {self.summary}"




class NewsletterSubscriber(models.Model):
    email = models.EmailField()
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="newsletter_subscribers",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=False)
    is_confirmed = models.BooleanField(default=False)
    confirmation_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["email", "tenant"],
                name="unique_newsletter_subscriber_per_tenant",
            )
        ]

    def __str__(self):
        return self.email