import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET,require_POST
from django.db import transaction
from .models import Product,Order,OrderItem
from .serializers import product_data
@require_GET
def products(request):
 qs=Product.objects.filter(active=True).order_by("id")
 category=request.GET.get("category")
 if category: qs=qs.filter(category__iexact=category)
 return JsonResponse([product_data(p) for p in qs],safe=False)
@csrf_exempt
@require_POST
def create_order(request):
 try: data=json.loads(request.body or "{}")
 except json.JSONDecodeError: return JsonResponse({"detail":"Invalid JSON request."},status=400)
 required=["name","phone","address","city","payment_method","items"]
 missing=[x for x in required if not data.get(x)]
 if missing: return JsonResponse({"detail":"Missing required fields: "+", ".join(missing)},status=400)
 allowed=[x[0] for x in Order.PAYMENT_CHOICES]
 if data["payment_method"] not in allowed: return JsonResponse({"detail":"Unsupported payment method."},status=400)
 if not isinstance(data["items"],list) or not data["items"]: return JsonResponse({"detail":"Your cart is empty."},status=400)
 try:
  with transaction.atomic():
   order=Order.objects.create(customer_name=str(data["name"])[:160],phone=str(data["phone"])[:30],email=str(data.get("email",""))[:254],address=str(data["address"]),city=str(data["city"])[:100],payment_method=data["payment_method"],total=0,shipping_fee=max(0,min(int(data.get("shipping_fee",120)),1000)),discount=max(0,min(int(data.get("discount",0)),550)),delivery_method=str(data.get("delivery_method","Standard Courier"))[:40])
   total=0
   for item in data["items"]:
    product=Product.objects.get(pk=int(item["product_id"]),active=True)
    qty=int(item.get("quantity",1)); size=str(item.get("size","42"))
    if qty<1 or qty>50: raise ValueError("Quantity must be between 1 and 50.")
    if size not in ["39","40","41","42","43","44"]: raise ValueError("Invalid shoe size.")
    OrderItem.objects.create(order=order,product=product,quantity=qty,size=size,unit_price=product.price)
    total+=product.price*qty
   order.total=max(0,total+order.shipping_fee-order.discount);order.save(update_fields=["total"])
  return JsonResponse({"order_number":order.order_number,"total":order.total,"shipping_fee":order.shipping_fee,"discount":order.discount,"delivery_method":order.delivery_method,"payment_method":order.payment_method,"payment_status":order.payment_status,"status":order.status},status=201)
 except Product.DoesNotExist: return JsonResponse({"detail":"One of the products is unavailable."},status=400)
 except (ValueError,KeyError,TypeError) as e: return JsonResponse({"detail":str(e) or "Invalid order data."},status=400)
@require_GET
def health(request): return JsonResponse({"status":"ok","service":"T-Shoe API"})
