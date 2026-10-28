from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="sender_phone",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.AddField(
            model_name="order",
            name="transaction_id",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]
