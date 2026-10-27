import uuid
from django.conf import settings
from django.db import models


def generate_order_number():
    return uuid.uuid4().hex[:10].upper()


class Product(models.Model):
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80, default="Sneakers")
    brand = models.CharField(max_length=80, blank=True, default="")
    price = models.PositiveIntegerField()
    stock_quantity = models.PositiveIntegerField(default=0)
    image = models.URLField()
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Order(models.Model):
    PAYMENT_CHOICES = [
        ("bKash", "bKash"),
        ("Nagad", "Nagad"),
        ("Bank Account", "Bank Account"),
        ("Cash on Delivery", "Cash on Delivery"),
        ("Outlet Pick & Pay", "Outlet Pick & Pay"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]
    order_number = models.CharField(max_length=20, unique=True, default=generate_order_number, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="store_orders",
    )
    customer_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    address = models.TextField()
    area = models.CharField(max_length=160, blank=True)
    road = models.CharField(max_length=160, blank=True)
    house = models.CharField(max_length=160, blank=True)
    delivery_notes = models.TextField(blank=True)
    city = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_CHOICES)
    payment_status = models.CharField(max_length=20, default="unpaid")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total = models.PositiveIntegerField(default=0)
    shipping_fee = models.PositiveIntegerField(default=0)
    discount = models.PositiveIntegerField(default=0)
    delivery_method = models.CharField(max_length=40, default="Standard Courier")
    pickup_outlet = models.CharField(max_length=20, blank=True, choices=[
        ("Rajshahi", "Rajshahi"),
        ("Bogura", "Bogura"),
    ])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order_number} - {self.customer_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    size = models.CharField(max_length=8, default="42")
    unit_price = models.PositiveIntegerField()


class PaymentAttempt(models.Model):
    PROVIDERS = [("bkash", "bKash"), ("nagad", "Nagad")]
    STATUSES = [
        ("created", "Created"),
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payment_attempts")
    provider = models.CharField(max_length=10, choices=PROVIDERS)
    status = models.CharField(max_length=12, choices=STATUSES, default="created")
    provider_payment_id = models.CharField(max_length=128, blank=True, db_index=True)
    provider_transaction_id = models.CharField(max_length=128, blank=True)
    amount = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
