from django.db import migrations


class Migration(migrations.Migration):
    """
    Merge the independent manual-payment and stock-reservation migration branches.
    No database operations are needed; this records that both branches are applied.
    """

    dependencies = [
        ("store", "0002_manual_payment_reference"),
        ("store", "0006_order_stock_reserved"),
    ]

    operations = []
