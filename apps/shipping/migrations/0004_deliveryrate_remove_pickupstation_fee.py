from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("shipping", "0003_rename_shipping_pi_tenant__6c2975_idx_shipping_pi_tenant__16599c_idx_and_more"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="pickupstation",
            name="fee",
        ),
        migrations.CreateModel(
            name="DeliveryRate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "region",
                    models.CharField(
                        choices=[
                            ("kampala_area", "Kampala Area"),
                            ("entebbe_area", "Entebbe Area"),
                            ("central_region", "Central Region"),
                            ("eastern_region", "Eastern Region"),
                            ("northern_region", "Northern Region"),
                            ("western_region", "Western Region"),
                            ("rest_of_kampala", "Rest of Kampala"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                ("city", models.CharField(blank=True, db_index=True, max_length=100)),
                ("area", models.CharField(blank=True, db_index=True, max_length=100)),
                (
                    "fee",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[MinValueValidator(Decimal("0.00"))],
                    ),
                ),
                ("estimated_days", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="delivery_rates",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "ordering": ["region", "city", "area", "fee", "estimated_days", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="deliveryrate",
            index=models.Index(
                fields=["tenant", "is_active"],
                name="ship_delrate_tenant_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="deliveryrate",
            index=models.Index(
                fields=["tenant", "region", "city", "area"],
                name="ship_delrate_tenant_loc_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="deliveryrate",
            constraint=models.UniqueConstraint(
                fields=("tenant", "region", "city", "area"),
                name="unique_delivery_rate_per_location",
            ),
        ),
    ]
