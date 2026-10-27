from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("store", "0004_seed_catalog_products")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="brand",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="product",
            name="stock_quantity",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
