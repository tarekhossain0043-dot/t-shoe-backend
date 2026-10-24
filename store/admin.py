from django.contrib import admin
from .models import Product,Order,OrderItem
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
 list_display=("name","category","price","active")
 list_filter=("category","active")
 search_fields=("name",)
class OrderItemInline(admin.TabularInline):
 model=OrderItem
 extra=0
 readonly_fields=("product","quantity","size","unit_price")
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
 list_display=("order_number","customer_name","phone","total","payment_method","payment_status","status","created_at")
 list_filter=("status","payment_method","payment_status")
 search_fields=("order_number","customer_name","phone")
 inlines=[OrderItemInline]
