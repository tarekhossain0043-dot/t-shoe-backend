from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import CustomerProductAction, Order, OrderItem, PaymentAttempt, Product, StoreNotification


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "category", "price", "stock_quantity", "active", "created_at")
    list_filter = ("brand", "category", "active")
    search_fields = ("name", "brand", "category")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "quantity", "size", "unit_price")

    def has_add_permission(self, request, obj=None):
        return False


class PaymentAttemptInline(admin.TabularInline):
    model = PaymentAttempt
    extra = 0
    can_delete = False
    readonly_fields = (
        "provider",
        "status",
        "provider_payment_id",
        "provider_transaction_id",
        "amount",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer_name",
        "phone",
        "city",
        "area",
        "delivery_method",
        "total",
        "payment_method",
        "payment_status",
        "status",
        "created_at",
    )
    list_filter = ("status", "payment_method", "payment_status", "delivery_method", "created_at")
    search_fields = ("order_number", "customer_name", "phone", "email", "city", "area", "road", "house", "delivery_notes", "user__email")
    readonly_fields = ("order_number", "created_at")
    inlines = [OrderItemInline, PaymentAttemptInline]
    date_hierarchy = "created_at"


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "provider_payment_id",
        "order",
        "provider",
        "status",
        "amount",
        "provider_transaction_id",
        "created_at",
        "updated_at",
    )
    list_filter = ("provider", "status", "created_at")
    search_fields = (
        "provider_payment_id",
        "provider_transaction_id",
        "order__order_number",
        "order__customer_name",
        "order__phone",
    )
    readonly_fields = (
        "order",
        "provider",
        "status",
        "provider_payment_id",
        "provider_transaction_id",
        "amount",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


User = get_user_model()
if not admin.site.is_registered(User):
    admin.site.register(User, UserAdmin)



@admin.register(StoreNotification)
class StoreNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "active", "created_at", "updated_at")
    list_filter = ("level", "active", "created_at")
    search_fields = ("title", "message")


@admin.register(CustomerProductAction)
class CustomerProductActionAdmin(admin.ModelAdmin):
    list_display = ("action", "product", "session_key", "user", "active", "updated_at")
    list_filter = ("action", "active", "updated_at")
    search_fields = ("product__name", "session_key", "user__email")
    readonly_fields = ("session_key", "product", "action", "user", "created_at", "updated_at")
