import uuid
from django.db import models
def generate_order_number():
 return uuid.uuid4().hex[:10].upper()

class Product(models.Model):
 name=models.CharField(max_length=160)
 category=models.CharField(max_length=80,default="Sneakers")
 price=models.PositiveIntegerField()
 image=models.URLField()
 description=models.TextField(blank=True)
 active=models.BooleanField(default=True)
 created_at=models.DateTimeField(auto_now_add=True)
 def __str__(self): return self.name
class Order(models.Model):
 PAYMENT_CHOICES=[("bKash","bKash"),("Nagad","Nagad"),("Bank Account","Bank Account"),("Cash on Delivery","Cash on Delivery")]
 STATUS_CHOICES=[("pending","Pending"),("confirmed","Confirmed"),("shipped","Shipped"),("delivered","Delivered"),("cancelled","Cancelled")]
 order_number=models.CharField(max_length=20,unique=True,default=generate_order_number,editable=False)
 customer_name=models.CharField(max_length=160)
 phone=models.CharField(max_length=30)
 email=models.EmailField(blank=True)
 address=models.TextField()
 city=models.CharField(max_length=100)
 payment_method=models.CharField(max_length=30,choices=PAYMENT_CHOICES)
 payment_status=models.CharField(max_length=20,default="unpaid")
 status=models.CharField(max_length=20,choices=STATUS_CHOICES,default="pending")
 total=models.PositiveIntegerField(default=0)
 shipping_fee=models.PositiveIntegerField(default=0)
 discount=models.PositiveIntegerField(default=0)
 delivery_method=models.CharField(max_length=40,default="Standard Courier")
 created_at=models.DateTimeField(auto_now_add=True)
 def __str__(self): return f"{self.order_number} - {self.customer_name}"
class OrderItem(models.Model):
 order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name="items")
 product=models.ForeignKey(Product,on_delete=models.PROTECT)
 quantity=models.PositiveIntegerField(default=1)
 size=models.CharField(max_length=8,default="42")
 unit_price=models.PositiveIntegerField()
