from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Order, OrderItem, Product
from .serializers import product_data


DELIVERY_FEES = {
    "Inside Hub": 120,
    "Inside Dhaka Metro": 150,
    "Nationwide": 200,
    "Hub Pickup": 0,
}
COUPON_DISCOUNTS = {
    "TSHOE10": 500,
    "NEWKE10": 500,
    "NEWKEDHAKA10": 550,
}
SHOE_SIZES = {"39", "40", "41", "42", "42.5", "43", "44", "45", "46"}
ONLINE_PAYMENT_METHODS = {"bKash", "Nagad"}


@require_GET
def products(request):
    queryset = Product.objects.filter(active=True).order_by("id")
    category = request.GET.get("category")
    if category:
        queryset = queryset.filter(category__iexact=category)
    return JsonResponse([product_data(product) for product in queryset], safe=False)


def _order_data(order):
    status_labels = {
        "pending": "Processing",
        "confirmed": "Processing",
        "shipped": "In Transit",
        "delivered": "Completed",
        "cancelled": "Cancelled",
    }
    items = [
        {
            "product": {**product_data(item.product), "price": item.unit_price},
            "qty": item.quantity,
            "size": item.size,
        }
        for item in order.items.select_related("product").all()
    ]
    return {
        "orderNumber": order.order_number,
        "items": items,
        "customer": {
            "name": order.customer_name,
            "phone": order.phone,
            "email": order.email,
            "city": order.city,
            "area": order.area or order.address,
            "road": order.road,
            "house": order.house,
            "notes": order.delivery_notes,
        },
        "subtotal": sum(item["product"]["price"] * item["qty"] for item in items),
        "shipping": order.shipping_fee,
        "discount": order.discount,
        "total": order.total,
        "payment": order.payment_method,
        "paymentStatus": order.payment_status,
        "senderPhone": order.sender_phone,
        "transactionId": order.transaction_id,
        "delivery": order.delivery_method,
        "pickupOutlet": order.pickup_outlet,
        "placedAt": order.created_at.isoformat(),
        "status": status_labels[order.status],
    }


@api_view(["POST"])
@permission_classes([AllowAny])
def create_order(request):
    data = request.data
    required = ("name", "phone", "city", "payment_method", "items")
    missing = [key for key in required if not data.get(key)]
    if missing:
        return Response({"detail": "Missing required fields: " + ", ".join(missing)}, status=status.HTTP_400_BAD_REQUEST)

    payment_method = str(data["payment_method"])
    if payment_method not in {"Cash on Delivery", "bKash", "Nagad", "Outlet Pick & Pay"}:
        return Response({"detail": "Choose a supported payment method."}, status=status.HTTP_400_BAD_REQUEST)
    sender_phone = str(data.get("sender_phone", "")).strip()
    transaction_id = str(data.get("transaction_id", "")).strip()
    if payment_method in ONLINE_PAYMENT_METHODS and (not sender_phone or not transaction_id):
        return Response({"detail": "Sender phone and transaction ID are required for manual payment."}, status=status.HTTP_400_BAD_REQUEST)
    if len(sender_phone) > 30 or len(transaction_id) > 128:
        return Response({"detail": "Sender phone or transaction ID is too long."}, status=status.HTTP_400_BAD_REQUEST)

    items = data["items"]
    if not isinstance(items, list) or not items:
        return Response({"detail": "Your cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

    delivery_method = str(data.get("delivery_method", ""))
    if delivery_method not in DELIVERY_FEES:
        return Response({"detail": "Choose a valid delivery method."}, status=status.HTTP_400_BAD_REQUEST)
    pickup_outlet = str(data.get("pickup_outlet", "")).strip()
    if payment_method == "Outlet Pick & Pay":
        if delivery_method != "Hub Pickup":
            return Response(
                {"detail": "Choose Hub Pickup to pay at an outlet."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if pickup_outlet not in {"Rajshahi", "Bogura"}:
            return Response(
                {"detail": "Choose Rajshahi or Bogura as your pickup outlet."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    elif pickup_outlet:
        return Response(
            {"detail": "An outlet can only be selected for Outlet Pick & Pay."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    coupon_code = str(data.get("coupon_code", "")).strip().upper()
    if coupon_code and coupon_code not in COUPON_DISCOUNTS:
        return Response({"detail": "That coupon code is not valid."}, status=status.HTTP_400_BAD_REQUEST)

    name = str(data["name"]).strip()
    phone = str(data["phone"]).strip()
    area = str(data.get("area", "")).strip()
    road = str(data.get("road", "")).strip()
    house = str(data.get("house", "")).strip()
    notes = str(data.get("notes", "")).strip()
    address = str(data.get("address", "")).strip()
    if not address:
        address = ", ".join(part for part in (house, road, area, notes) if part)
    city = str(data["city"]).strip()
    email = str(data.get("email", "")).strip()
    if not name or len(name) > 160 or not phone or len(phone) > 30 or not address or not city or len(city) > 100:
        return Response({"detail": "Enter valid delivery and contact details."}, status=status.HTTP_400_BAD_REQUEST)
    if email:
        try:
            validate_email(email)
        except ValidationError:
            return Response({"detail": "Enter a valid email address."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                customer_name=name,
                phone=phone,
                email=email,
                address=address,
                area=area,
                road=road,
                house=house,
                delivery_notes=notes,
                city=city,
                payment_method=payment_method,
                payment_status="pending" if payment_method in ONLINE_PAYMENT_METHODS else "unpaid",
                sender_phone=sender_phone,
                transaction_id=transaction_id,
                shipping_fee=DELIVERY_FEES[delivery_method],
                delivery_method=delivery_method,
                pickup_outlet=pickup_outlet,
            )
            subtotal = 0
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Invalid cart item.")
                product_id = int(item["product_id"])
                quantity = int(item.get("quantity", 1))
                size = str(item.get("size", "42"))
                if quantity < 1 or quantity > 50:
                    raise ValueError("Quantity must be between 1 and 50.")
                if size not in SHOE_SIZES:
                    raise ValueError("Invalid shoe size.")
                product = Product.objects.get(pk=product_id, active=True)
                if product.stock_quantity < quantity:
                    raise ValueError(f"Only {product.stock_quantity} unit(s) of {product.name} are currently in stock.")
                product.stock_quantity -= quantity
                product.save(update_fields=["stock_quantity"])
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    size=size,
                    unit_price=product.price,
                )
                subtotal += product.price * quantity
            order.discount = min(COUPON_DISCOUNTS.get(coupon_code, 0), subtotal)
            order.total = max(0, subtotal + order.shipping_fee - order.discount)
            order.stock_reserved = True
            order.save(update_fields=["discount", "total", "stock_reserved"])
    except Product.DoesNotExist:
        return Response({"detail": "One of the products is unavailable."}, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, KeyError, TypeError, OverflowError) as error:
        return Response({"detail": str(error) or "Invalid order data."}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "order_number": order.order_number,
            "total": order.total,
            "shipping_fee": order.shipping_fee,
            "discount": order.discount,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "status": order.status,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_history(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items__product").order_by("-created_at")
    return Response({"orders": [_order_data(order) for order in orders]})


@require_GET
def health(request):
    return JsonResponse({"status": "ok", "service": "T-Shoe API"})


# All management endpoints below are restricted to Django staff/superusers.
from datetime import timedelta
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework.permissions import IsAdminUser


def _admin_product_data(product):
    return {
        **product_data(product),
        "active": product.active,
        "stock_quantity": product.stock_quantity,
        "created_at": product.created_at.isoformat(),
    }


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_dashboard(request):
    today = timezone.localdate()
    start = today - timedelta(days=29)
    delivered = Order.objects.filter(status="delivered")
    non_cancelled = Order.objects.exclude(status="cancelled")
    daily_orders = []
    daily_sales = []
    for offset in range(30):
        day = start + timedelta(days=offset)
        day_orders = Order.objects.filter(created_at__date=day).exclude(status="cancelled")
        day_delivered = delivered.filter(created_at__date=day)
        daily_orders.append({"date": day.isoformat(), "orders": day_orders.count()})
        daily_sales.append({"date": day.isoformat(), "sales": day_delivered.aggregate(total=Sum("total"))["total"] or 0})
    best_sellers = list(
        OrderItem.objects.filter(order__status="delivered")
        .values("product_id", "product__name")
        .annotate(quantity=Sum("quantity"), revenue=Sum(F("unit_price") * F("quantity")) )
        .order_by("-quantity")[:8]
    )
    return Response({
        "metrics": {
            "total_sales": delivered.aggregate(total=Sum("total"))["total"] or 0,
            "total_order_value": non_cancelled.aggregate(total=Sum("total"))["total"] or 0,
            "total_sale_items": OrderItem.objects.filter(order__status="delivered").aggregate(total=Sum("quantity"))["total"] or 0,
            "total_products": Product.objects.filter(active=True).count(),
            "in_stock_products": Product.objects.filter(active=True, stock_quantity__gt=0).count(),
            "out_of_stock_products": Product.objects.filter(active=True, stock_quantity=0).count(),
            "total_orders": Order.objects.count(),
            "pending_orders": Order.objects.filter(status="pending").count(),
            "cancelled_orders": Order.objects.filter(status="cancelled").count(),
            "customers": Order.objects.values("phone").distinct().count(),
            "pending_value": non_cancelled.filter(status__in=["pending", "confirmed", "shipped"]).aggregate(total=Sum("total"))["total"] or 0,
        },
        "daily_orders": daily_orders,
        "daily_sales": daily_sales,
        "best_sellers": best_sellers,
    })


@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def admin_products(request):
    if request.method == "GET":
        products_qs = Product.objects.all().order_by("-created_at")
        search = str(request.query_params.get("search", "")).strip()
        if search:
            from django.db.models import Q
            products_qs = products_qs.filter(Q(name__icontains=search) | Q(brand__icontains=search) | Q(category__icontains=search))
        return Response([_admin_product_data(product) for product in products_qs])

    data = request.data
    try:
        name = str(data.get("name", "")).strip()
        category = str(data.get("category", "Sneakers")).strip()
        brand = str(data.get("brand", "")).strip()
        price = int(data.get("price", 0))
        stock_quantity = int(data.get("stock_quantity", 0))
        image = str(data.get("image", "")).strip()
        description = str(data.get("description", "")).strip()
        if not name or len(name) > 160 or not category or len(category) > 80:
            raise ValueError("Enter a valid product name and category.")
        if price < 0 or stock_quantity < 0:
            raise ValueError("Price and stock must be zero or greater.")
        if not image.startswith(("https://", "http://")):
            raise ValueError("Enter a valid product image URL.")
        product = Product.objects.create(
            name=name, category=category, brand=brand[:80], price=price,
            stock_quantity=stock_quantity, image=image, description=description, active=True,
        )
        return Response(_admin_product_data(product), status=status.HTTP_201_CREATED)
    except (TypeError, ValueError, OverflowError) as error:
        return Response({"detail": str(error) or "Invalid product data."}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAdminUser])
def admin_product_detail(request, product_id):
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        # Keep order history and its protected product references intact.
        product.active = False
        product.save(update_fields=["active"])
        return Response({"detail": "Product archived and hidden from the storefront."}, status=status.HTTP_200_OK)

    data = request.data
    try:
        if "name" in data:
            product.name = str(data["name"]).strip()
            if not product.name or len(product.name) > 160:
                raise ValueError("Enter a valid product name.")
        if "category" in data:
            product.category = str(data["category"]).strip()
        if "brand" in data:
            product.brand = str(data["brand"]).strip()[:80]
        if "price" in data:
            product.price = int(data["price"])
            if product.price < 0:
                raise ValueError("Price must be zero or greater.")
        if "stock_quantity" in data:
            product.stock_quantity = int(data["stock_quantity"])
            if product.stock_quantity < 0:
                raise ValueError("Stock must be zero or greater.")
        if "image" in data:
            product.image = str(data["image"]).strip()
            if not product.image.startswith(("https://", "http://")):
                raise ValueError("Enter a valid product image URL.")
        if "description" in data:
            product.description = str(data["description"]).strip()
        if "active" in data:
            product.active = bool(data["active"])
        product.save()
        return Response(_admin_product_data(product))
    except (TypeError, ValueError, OverflowError) as error:
        return Response({"detail": str(error) or "Invalid product data."}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_orders(request):
    queryset = Order.objects.prefetch_related("items__product").order_by("-created_at")
    status_filter = str(request.query_params.get("status", "")).strip()
    if status_filter and status_filter in {choice[0] for choice in Order.STATUS_CHOICES}:
        queryset = queryset.filter(status=status_filter)
    search = str(request.query_params.get("search", "")).strip()
    if search:
        from django.db.models import Q
        queryset = queryset.filter(
            Q(order_number__icontains=search) | Q(customer_name__icontains=search)
            | Q(phone__icontains=search) | Q(email__icontains=search)
        )
    results = []
    for order in queryset[:500]:
        item = _order_data(order)
        item["status"] = order.status
        results.append(item)
    return Response(results)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAdminUser])
def admin_order_detail(request, order_number):
    try:
        order = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        with transaction.atomic():
            if order.stock_reserved:
                for item in order.items.select_related("product").all():
                    product = Product.objects.select_for_update().get(pk=item.product_id)
                    product.stock_quantity += item.quantity
                    product.save(update_fields=["stock_quantity"])
            order.delete()
        return Response({"detail": "Order permanently deleted and reserved stock restored."}, status=status.HTTP_200_OK)
    next_status = str(request.data.get("status", "")).strip()
    valid_statuses = {choice[0] for choice in Order.STATUS_CHOICES}
    if next_status not in valid_statuses:
        return Response({"detail": "Choose a valid order status."}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        if next_status == "cancelled" and order.stock_reserved:
            for item in order.items.select_related("product").all():
                product = Product.objects.select_for_update().get(pk=item.product_id)
                product.stock_quantity += item.quantity
                product.save(update_fields=["stock_quantity"])
            order.stock_reserved = False
            order.save(update_fields=["status", "stock_reserved"])
        elif order.status == "cancelled" and next_status != "cancelled" and not order.stock_reserved:
            items = list(order.items.select_related("product").all())
            for item in items:
                product = Product.objects.select_for_update().get(pk=item.product_id)
                if product.stock_quantity < item.quantity:
                    return Response({"detail": f"Not enough stock to reopen this order for {product.name}."}, status=status.HTTP_400_BAD_REQUEST)
            for item in items:
                product = Product.objects.select_for_update().get(pk=item.product_id)
                product.stock_quantity -= item.quantity
                product.save(update_fields=["stock_quantity"])
            order.stock_reserved = True
            order.save(update_fields=["status", "stock_reserved"])
        else:
            order.status = next_status
            order.save(update_fields=["status"])
    return Response(_order_data(order))
