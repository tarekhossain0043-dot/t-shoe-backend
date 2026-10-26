from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0002_order_pickup_outlet_order_user_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="area",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="order",
            name="road",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="order",
            name="house",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_notes",
            field=models.TextField(blank=True),
        ),
    ]
