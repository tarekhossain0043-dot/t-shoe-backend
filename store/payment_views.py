import logging
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Order, PaymentAttempt
from .payment_services import (
    GatewayError,
    start_bkash_payment,
    start_nagad_payment,
    verify_bkash_payment,
    verify_nagad_payment,
)


logger = logging.getLogger(__name__)
PROVIDERS = {
    "bkash": ("bKash", start_bkash_payment),
    "nagad": ("Nagad", start_nagad_payment),
}


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_payment(request, provider):
    provider_config = PROVIDERS.get(provider)
    if not provider_config:
        return Response({"detail": "Unsupported payment provider."}, status=status.HTTP_404_NOT_FOUND)
    payment_method, start_gateway = provider_config
    order_number = str(request.data.get("order_number", "")).strip()
    order = Order.objects.filter(order_number=order_number, user=request.user).first()
    if not order:
        return Response({"detail": "Order not found for this account."}, status=status.HTTP_404_NOT_FOUND)
    if order.payment_method != payment_method:
        return Response({"detail": "This order uses a different payment method."}, status=status.HTTP_400_BAD_REQUEST)
    if order.payment_status == "paid":
        return Response({"detail": "This order has already been paid."}, status=status.HTTP_409_CONFLICT)

    attempt = PaymentAttempt.objects.create(
        order=order,
        provider=provider,
        amount=order.total,
    )
    try:
        redirect_url = start_gateway(order, attempt)
    except GatewayError as error:
        attempt.status = "failed"
        attempt.save(update_fields=["status", "updated_at"])
        logger.warning("%s payment initialization failed for order %s: %s", provider, order.order_number, error)
        return Response({"detail": str(error)}, status=status.HTTP_502_BAD_GATEWAY)
    return Response({"redirect_url": redirect_url}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def complete_bkash_payment(request):
    order_number = str(request.data.get("order_number", "")).strip()
    payment_id = str(request.data.get("paymentID", "")).strip()
    if not order_number or not payment_id:
        return Response({"detail": "Missing bKash payment reference."}, status=status.HTTP_400_BAD_REQUEST)
    attempt = PaymentAttempt.objects.filter(
        order__order_number=order_number,
        order__user=request.user,
        provider="bkash",
        provider_payment_id=payment_id,
    ).select_related("order").first()
    if not attempt:
        return Response({"detail": "Payment reference not found for this account."}, status=status.HTTP_404_NOT_FOUND)
    try:
        verify_bkash_payment(attempt, payment_id)
    except GatewayError as error:
        logger.warning("bKash verification failed for order %s: %s", order_number, error)
        return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"order_number": order_number, "payment_status": "paid"})


def _frontend_payment_result(order_number, result, *, payment_id=""):
    query = {"order_number": order_number, "provider": result}
    if payment_id:
        query["paymentID"] = payment_id
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/payment/callback?{urlencode(query)}")


@require_GET
def bkash_callback(request):
    order_number = request.GET.get("order_number", "")
    payment_id = request.GET.get("paymentID", "")
    provider_status = request.GET.get("status", "")
    if not order_number or not payment_id or provider_status.lower() != "success":
        return _frontend_payment_result(order_number, "cancelled")
    return _frontend_payment_result(order_number, "return", payment_id=payment_id)


@require_GET
def nagad_callback(request):
    payment_reference = (
        request.GET.get("payment_ref_id")
        or request.GET.get("paymentReferenceId")
        or request.GET.get("paymentReferenceID")
        or ""
    )
    attempt = PaymentAttempt.objects.filter(
        provider="nagad",
        provider_payment_id=payment_reference,
    ).select_related("order").first()
    if not attempt:
        logger.warning("Nagad callback did not match a local payment attempt.")
        return _frontend_payment_result("", "failed")
    try:
        verify_nagad_payment(attempt)
    except GatewayError as error:
        logger.warning("Nagad verification failed for order %s: %s", attempt.order.order_number, error)
        return _frontend_payment_result(attempt.order.order_number, "failed")
    return _frontend_payment_result(attempt.order.order_number, "success")

