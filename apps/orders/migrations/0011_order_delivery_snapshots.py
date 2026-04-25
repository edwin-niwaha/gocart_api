from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0010_order_pricing_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="address_area",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_station_address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_station_area",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_station_city",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_station_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_station_opening_hours",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_station_phone",
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
