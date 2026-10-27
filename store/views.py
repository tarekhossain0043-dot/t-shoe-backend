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
    if payment_method not in {choice[0] for choice in Order.PAYMENT_CHOICES}:
        return Response({"detail": "Unsupported payment method."}, status=status.HTTP_400_BAD_REQUEST)
    if payment_method in ONLINE_PAYMENT_METHODS and not request.user.is_authenticated:
        return Response(
            {"detail": "Sign in before placing a bKash or Nagad order."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

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
            order.save(update_fields=["discount", "total"])
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
