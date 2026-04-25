from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("addresses", "0003_remove_customeraddress_addresses_c_created_4c4c08_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="customeraddress",
            name="area",
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddIndex(
            model_name="customeraddress",
            index=models.Index(
                fields=["user", "area"],
                name="address_user_area_idx",
            ),
        ),
    ]
