import base64
import json
import secrets
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Order, PaymentAttempt


class GatewayError(Exception):
    pass


class GatewayTimeout(GatewayError):
    pass


def _post_json(url, *, headers=None, body=None, timeout=30):
    try:
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as error:
        raise GatewayTimeout("The payment gateway did not respond in time.") from error
    except (requests.RequestException, ValueError) as error:
        raise GatewayError("The payment gateway request failed.") from error
    if not isinstance(data, dict):
        raise GatewayError("The payment gateway returned an invalid response.")
    return data


def _get_json(url, *, headers=None, timeout=30):
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as error:
        raise GatewayTimeout("The payment gateway did not respond in time.") from error
    except (requests.RequestException, ValueError) as error:
        raise GatewayError("The payment gateway request failed.") from error
    if not isinstance(data, dict):
        raise GatewayError("The payment gateway returned an invalid response.")
    return data


def _require_bkash_credentials():
    values = (
        settings.BKASH_APP_KEY,
        settings.BKASH_APP_SECRET,
        settings.BKASH_USERNAME,
        settings.BKASH_PASSWORD,
    )
    if not all(values):
        raise GatewayError("bKash sandbox credentials are not configured on the server.")


def _bkash_token():
    _require_bkash_credentials()
    token = cache.get("bkash_access_token")
    if token:
        return token
    data = _post_json(
        f"{settings.BKASH_BASE_URL}/auth/grant-token",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "username": settings.BKASH_USERNAME,
            "password": settings.BKASH_PASSWORD,
        },
        body={"app_key": settings.BKASH_APP_KEY, "app_secret": settings.BKASH_APP_SECRET},
    )
    token = data.get("id_token")
    if not token:
        raise GatewayError("bKash did not issue an authorization token.")
    try:
        expires_in = int(data.get("expires_in", 3600))
    except (TypeError, ValueError):
        expires_in = 3600
    cache.set("bkash_access_token", token, timeout=max(60, min(expires_in - 60, 3500)))
    return token


def _bkash_headers(token):
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": token,
        "X-App-Key": settings.BKASH_APP_KEY,
    }


def start_bkash_payment(order, attempt):
    token = _bkash_token()
    callback_url = (
        f"{settings.BACKEND_PUBLIC_URL}{reverse('bkash-callback')}"
        f"?order_number={order.order_number}"
    )
    data = _post_json(
        f"{settings.BKASH_BASE_URL}/payment/create",
        headers=_bkash_headers(token),
        body={
            "mode": "0011",
            "payerReference": order.phone,
            "callbackURL": callback_url,
            "amount": str(order.total),
            "currency": "BDT",
            "intent": "sale",
            "merchantInvoiceNumber": order.order_number,
        },
    )
    payment_id = data.get("paymentID")
    redirect_url = data.get("bkashURL")
    if (
        not payment_id
        or not redirect_url
        or urlparse(redirect_url).scheme != "https"
        or not urlparse(redirect_url).netloc
    ):
        raise GatewayError("bKash did not return a payment link.")
    attempt.provider_payment_id = str(payment_id)
    attempt.status = "pending"
    attempt.save(update_fields=["provider_payment_id", "status", "updated_at"])
    return redirect_url


def _check_bkash_result(data, order, payment_id):
    invoice = data.get("merchantInvoiceNumber") or data.get("merchantInvoice")
    if (
        data.get("paymentID", data.get("paymentId")) != payment_id
        or data.get("transactionStatus") != "Completed"
        or invoice != order.order_number
        or str(data.get("currency", "")).upper() != "BDT"
    ):
        raise GatewayError("bKash payment verification did not match this order.")
    try:
        amount = Decimal(str(data.get("amount")))
    except (InvalidOperation, TypeError):
        raise GatewayError("bKash returned an invalid payment amount.")
    if amount != Decimal(order.total):
        raise GatewayError("The verified bKash amount does not match this order.")
    transaction_id = data.get("trxId")
    if not transaction_id:
        raise GatewayError("bKash did not return a transaction reference.")
    return str(transaction_id)


def verify_bkash_payment(attempt, payment_id):
    if attempt.provider_payment_id != payment_id:
        raise GatewayError("This payment reference does not belong to the order.")
    token = _bkash_token()
    try:
        result = _post_json(
            f"{settings.BKASH_BASE_URL}/payment/execute",
            headers=_bkash_headers(token),
            body={"paymentId": payment_id},
        )
    except GatewayError:
        result = _post_json(
            f"{settings.BKASH_BASE_URL}/query/payment",
            headers=_bkash_headers(token),
            body={"paymentId": payment_id},
        )
    transaction_id = _check_bkash_result(result, attempt.order, payment_id)
    _mark_attempt_paid(attempt, transaction_id)


def _load_nagad_keys():
    private_path = settings.NAGAD_MERCHANT_PRIVATE_KEY_PATH
    public_path = settings.NAGAD_PG_PUBLIC_KEY_PATH
    if not private_path or not public_path:
        raise GatewayError("Nagad sandbox certificate paths are not configured on the server.")
    try:
        private_key = serialization.load_pem_private_key(
            Path(private_path).read_bytes(),
            password=None,
        )
        public_key = serialization.load_pem_public_key(Path(public_path).read_bytes())
    except (OSError, ValueError, TypeError) as error:
        raise GatewayError("Nagad merchant/gateway certificates could not be loaded.") from error
    return private_key, public_key


def _nagad_encrypt(value, public_key):
    payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
    encrypted = public_key.encrypt(payload, padding.PKCS1v15())
    return base64.b64encode(encrypted).decode("ascii")


def _nagad_sign(value, private_key):
    payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


def _nagad_decrypt(value, private_key):
    try:
        plaintext = private_key.decrypt(base64.b64decode(value, validate=True), padding.PKCS1v15())
        decoded = json.loads(plaintext)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise GatewayError("Nagad returned data that could not be verified.") from error
    if not isinstance(decoded, dict):
        raise GatewayError("Nagad returned an invalid response.")
    return decoded


def _require_nagad_credentials():
    if not settings.NAGAD_MERCHANT_ID:
        raise GatewayError("Nagad sandbox merchant ID is not configured on the server.")
    return _load_nagad_keys()


def start_nagad_payment(order, attempt):
    if not settings.NAGAD_MERCHANT_ID:
        raise GatewayError("Nagad sandbox merchant ID is not configured on the server.")
    private_key, public_key = _require_nagad_credentials()
    merchant_id = settings.NAGAD_MERCHANT_ID
    date_time = timezone.localtime().strftime("%Y%m%d%H%M%S")
    challenge = "".join(secrets.choice("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(40))
    init_data = {
        "merchantId": merchant_id,
        "datetime": date_time,
        "orderId": order.order_number,
        "challenge": challenge,
    }
    init_payload = {
        "dateTime": date_time,
        "sensitiveData": _nagad_encrypt(init_data, public_key),
        "signature": _nagad_sign(init_data, private_key),
    }
    if settings.NAGAD_MERCHANT_NUMBER:
        init_payload["accountNumber"] = settings.NAGAD_MERCHANT_NUMBER
    headers = {
        "Content-Type": "application/json",
        "X-KM-Api-Version": "v-0.2.0",
        "X-KM-IP-V4": settings.NAGAD_CLIENT_IP,
        "X-KM-Client-Type": "PC_WEB",
    }
    initialize_url = (
        f"{settings.NAGAD_API_BASE_URL}/api/dfs/check-out/initialize/"
        f"{merchant_id}/{order.order_number}"
    )
    initialized = _post_json(initialize_url, headers=headers, body=init_payload)
    encrypted_response = initialized.get("sensitiveData")
    if not encrypted_response:
        raise GatewayError("Nagad did not initialize this payment.")
    init_result = _nagad_decrypt(encrypted_response, private_key)
    payment_reference = init_result.get("paymentReferenceId")
    gateway_challenge = init_result.get("challenge")
    if not payment_reference or not gateway_challenge:
        raise GatewayError("Nagad returned an invalid payment reference.")

    complete_data = {
        "merchantId": merchant_id,
        "orderId": order.order_number,
        "currencyCode": "050",
        "amount": str(order.total),
        "challenge": gateway_challenge,
    }
    callback_url = (
        f"{settings.BACKEND_PUBLIC_URL}{reverse('nagad-callback')}"
    )
    complete_payload = {
        "sensitiveData": _nagad_encrypt(complete_data, public_key),
        "signature": _nagad_sign(complete_data, private_key),
        "merchantCallbackURL": callback_url,
        "additionalMerchantInfo": {"orderNumber": order.order_number},
    }
    completed = _post_json(
        f"{settings.NAGAD_API_BASE_URL}/api/dfs/check-out/complete/{payment_reference}",
        headers=headers,
        body=complete_payload,
    )
    redirect_url = completed.get("callBackUrl")
    if (
        completed.get("status") != "Success"
        or not redirect_url
        or urlparse(redirect_url).scheme != "https"
        or not urlparse(redirect_url).netloc
    ):
        raise GatewayError("Nagad could not create the payment link.")
    attempt.provider_payment_id = str(payment_reference)
    attempt.status = "pending"
    attempt.save(update_fields=["provider_payment_id", "status", "updated_at"])
    return redirect_url


def verify_nagad_payment(attempt):
    _require_nagad_credentials()
    reference = attempt.provider_payment_id
    if not reference:
        raise GatewayError("The Nagad payment reference is missing.")
    data = _get_json(
        f"{settings.NAGAD_API_BASE_URL}/api/dfs/verify/payment/{reference}",
        headers={
            "Accept": "application/json",
            "X-KM-Api-Version": "v-0.2.0",
            "X-KM-IP-V4": settings.NAGAD_CLIENT_IP,
            "X-KM-Client-Type": "PC_WEB",
        },
    )
    try:
        amount = Decimal(str(data.get("amount")))
    except (InvalidOperation, TypeError):
        raise GatewayError("Nagad returned an invalid payment amount.")
    transaction_id = data.get("issuerRef") or data.get("trxID") or data.get("transactionId")
    if (
        data.get("status") != "Success"
        or data.get("orderId") != attempt.order.order_number
        or str(data.get("currencyCode", "")) != "050"
        or amount != Decimal(attempt.order.total)
        or attempt.amount != attempt.order.total
        or not transaction_id
    ):
        raise GatewayError("Nagad payment verification did not match this order.")
    _mark_attempt_paid(attempt, str(transaction_id))


def _mark_attempt_paid(attempt, transaction_id):
    with transaction.atomic():
        locked_attempt = PaymentAttempt.objects.select_for_update().select_related("order").get(pk=attempt.pk)
        order = Order.objects.select_for_update().get(pk=locked_attempt.order_id)
        if locked_attempt.amount != order.total:
            raise GatewayError("The payment amount no longer matches this order.")
        if order.payment_status == "paid":
            if locked_attempt.status != "paid":
                raise GatewayError("This order has already been paid using another transaction.")
            return
        locked_attempt.status = "paid"
        locked_attempt.provider_transaction_id = transaction_id
        locked_attempt.save(update_fields=["status", "provider_transaction_id", "updated_at"])
        order.payment_status = "paid"
        update_fields = ["payment_status"]
        if order.status == "pending":
            order.status = "confirmed"
            update_fields.append("status")
        order.save(update_fields=update_fields)


def mark_attempt_failed(attempt):
    with transaction.atomic():
        locked_attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
        if locked_attempt.status != "paid":
            locked_attempt.status = "failed"
            locked_attempt.save(update_fields=["status", "updated_at"])
