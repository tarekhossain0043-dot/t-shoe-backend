from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("store", "0005_product_brand_stock_quantity")]

    operations = [
        migrations.AddField(
            model_name="order",
            name="stock_reserved",
            field=models.BooleanField(default=False),
        ),
    ]
