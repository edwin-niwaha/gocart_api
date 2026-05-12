from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("shipping", "0004_deliveryrate_remove_pickupstation_fee"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Shipment",
        ),
    ]
