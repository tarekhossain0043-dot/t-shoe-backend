from rest_framework.test import APITestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model
from unittest.mock import patch

from rest_framework_simplejwt.tokens import RefreshToken

from .models import Order, PaymentAttempt, Product


class MemberAuthenticationTests(APITestCase):
    register_url = "/api/auth/register/"
    login_url = "/api/auth/login/"
    refresh_url = "/api/auth/refresh/"
    logout_url = "/api/auth/logout/"
    profile_url = "/api/auth/me/"

    def setUp(self):
        cache.clear()

    def register(self):
        return self.client.post(
            self.register_url,
            {
                "name": "Test Member",
                "phone": "+880 1712 345678",
                "email": "member@example.com",
                "password": "correct-horse-42",
            },
            format="json",
        )

    def test_register_returns_tokens_and_protected_profile(self):
        response = self.register()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], "member@example.com")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        profile = self.client.get(self.profile_url)
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["user"]["phone"], "+8801712345678")

    def test_registration_rejects_duplicate_email(self):
        registration = self.register()
        self.assertEqual(registration.status_code, 201, registration.data)
        response = self.client.post(
            self.register_url,
            {
                "name": "Another Member",
                "phone": "+8801812345678",
                "email": "MEMBER@example.com",
                "password": "correct-horse-42",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409)

    def test_login_accepts_email_and_phone(self):
        self.register()
        for identifier in ("member@example.com", "+8801712345678"):
            response = self.client.post(
                self.login_url,
                {"identifier": identifier, "password": "correct-horse-42"},
                format="json",
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("access", response.data)

    def test_invalid_login_and_unauthenticated_profile_are_rejected(self):
        self.assertEqual(self.client.get(self.profile_url).status_code, 401)
        self.register()
        response = self.client.post(
            self.login_url,
            {"identifier": "member@example.com", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_local_frontend_origins_are_allowed_to_call_login_api(self):
        for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
            response = self.client.post(
                self.login_url,
                {"identifier": "nobody@example.com", "password": "invalid-password"},
                format="json",
                HTTP_ORIGIN=origin,
            )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)

    def test_refresh_rotates_token_and_logout_blacklists_it(self):
        tokens = self.register().data
        refreshed = self.client.post(self.refresh_url, {"refresh": tokens["refresh"]}, format="json")

        self.assertEqual(refreshed.status_code, 200)
        self.assertNotEqual(refreshed.data["refresh"], tokens["refresh"])
        self.assertEqual(
            self.client.post(self.refresh_url, {"refresh": tokens["refresh"]}, format="json").status_code,
            401,
        )
        self.assertEqual(
            self.client.post(self.logout_url, {"refresh": refreshed.data["refresh"]}, format="json").status_code,
            205,
        )
        self.assertEqual(
            self.client.post(self.refresh_url, {"refresh": refreshed.data["refresh"]}, format="json").status_code,
            401,
        )


class OrderAndPaymentTests(APITestCase):
    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.member = user_model.objects.create_user(
            username="+8801712345678",
            email="buyer@example.com",
            password="correct-horse-42",
        )
        self.other_member = user_model.objects.create_user(
            username="+8801812345678",
            email="other@example.com",
            password="correct-horse-42",
        )
        self.product = Product.objects.create(
            name="Test Sneaker",
            category="Sneakers",
            price=1000,
            image="https://example.com/shoe.jpg",
        )
        self.order_url = "/api/orders/"

    def authenticate(self, user=None):
        user = user or self.member
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def order_payload(self, payment_method="bKash"):
        return {
            "name": "Test Buyer",
            "phone": "+8801712345678",
            "email": "buyer@example.com",
            "address": "House 1, Road 2",
            "city": "Dhaka",
            "payment_method": payment_method,
            "delivery_method": "Nationwide",
            "shipping_fee": 0,
            "discount": 99999,
            "coupon_code": "TSHOE10",
            "items": [{"product_id": self.product.pk, "quantity": 2, "size": "42"}],
        }

    def create_member_order(self, user=None, payment_method="bKash"):
        self.authenticate(user)
        return self.client.post(self.order_url, self.order_payload(payment_method), format="json")

    def test_online_order_requires_jwt_and_server_calculates_total(self):
        denied = self.client.post(self.order_url, self.order_payload(), format="json")
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(Order.objects.count(), 0)

        response = self.create_member_order()
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(order_number=response.data["order_number"])
        self.assertEqual((order.total, order.shipping_fee, order.discount), (1700, 200, 500))
        self.assertEqual(order.payment_status, "pending")
        self.assertEqual(order.user, self.member)

    def test_history_is_limited_to_the_authenticated_order_owner(self):
        first = self.create_member_order()
        second = self.create_member_order(self.other_member)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        self.authenticate(self.member)
        response = self.client.get("/api/orders/history/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([order["orderNumber"] for order in response.data["orders"]], [first.data["order_number"]])

    def test_order_history_uses_the_price_saved_when_the_order_was_placed(self):
        created = self.create_member_order()
        self.product.price = 1500
        self.product.save(update_fields=["price"])

        self.authenticate(self.member)
        response = self.client.get("/api/orders/history/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["orders"][0]["subtotal"], 2000)
        self.assertEqual(response.data["orders"][0]["items"][0]["product"]["price"], 1000)

    def test_outlet_pickup_requires_a_pickup_delivery_and_selected_outlet(self):
        payload = self.order_payload(payment_method="Outlet Pick & Pay")
        payload["delivery_method"] = "Hub Pickup"
        missing_outlet = self.client.post(self.order_url, payload, format="json")
        self.assertEqual(missing_outlet.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

        payload["pickup_outlet"] = "Bogura"
        response = self.client.post(self.order_url, payload, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(order_number=response.data["order_number"])
        self.assertEqual(order.payment_method, "Outlet Pick & Pay")
        self.assertEqual(order.delivery_method, "Hub Pickup")
        self.assertEqual(order.pickup_outlet, "Bogura")
        self.assertEqual(order.payment_status, "unpaid")

    def test_bkash_cancellation_marks_only_the_attempt_failed(self):
        created = self.create_member_order()
        order = Order.objects.get(order_number=created.data["order_number"])
        attempt = PaymentAttempt.objects.create(
            order=order,
            provider="bkash",
            status="pending",
            provider_payment_id="cancelled-payment",
            amount=order.total,
        )

        response = self.client.get(
            "/api/payments/bkash/callback/",
            {"order_number": order.order_number, "paymentID": attempt.provider_payment_id, "status": "cancel"},
        )

        self.assertEqual(response.status_code, 302)
        attempt.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(attempt.status, "failed")
        self.assertEqual(order.payment_status, "pending")

    @patch("store.payment_services._get_json")
    @patch("store.payment_services._require_nagad_credentials", return_value=(None, None))
    def test_nagad_callback_verifies_with_provider_before_marking_order_paid(self, _credentials, get_json):
        created = self.create_member_order(payment_method="Nagad")
        order = Order.objects.get(order_number=created.data["order_number"])
        attempt = PaymentAttempt.objects.create(
            order=order,
            provider="nagad",
            status="pending",
            provider_payment_id="nagad-ref-123",
            amount=order.total,
        )
        get_json.return_value = {
            "status": "Success",
            "orderId": order.order_number,
            "currencyCode": "050",
            "amount": str(order.total),
            "issuerRef": "nagad-trx-123",
        }

        response = self.client.get(
            "/api/payments/nagad/callback/",
            {"payment_ref_id": attempt.provider_payment_id},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("provider=success", response["Location"])
        order.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.status, "confirmed")
        self.assertEqual(attempt.provider_transaction_id, "nagad-trx-123")

    @patch("store.payment_views.start_bkash_payment", return_value="https://sandbox.example/pay")
    def test_gateway_start_does_not_mark_order_paid_and_rejects_other_owner(self, start_payment):
        created = self.create_member_order()
        order_number = created.data["order_number"]

        self.authenticate(self.other_member)
        denied = self.client.post("/api/payments/bkash/start/", {"order_number": order_number}, format="json")
        self.assertEqual(denied.status_code, 404)

        self.authenticate(self.member)
        response = self.client.post("/api/payments/bkash/start/", {"order_number": order_number}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        order = Order.objects.get(order_number=order_number)
        self.assertEqual(order.payment_status, "pending")
        self.assertEqual(PaymentAttempt.objects.get(order=order).status, "created")

    @patch("store.payment_services._post_json")
    @patch("store.payment_services._bkash_token", return_value="sandbox-token")
    def test_bkash_only_marks_paid_after_matching_verified_response(self, _token, post_json):
        created = self.create_member_order()
        order = Order.objects.get(order_number=created.data["order_number"])
        attempt = PaymentAttempt.objects.create(
            order=order,
            provider="bkash",
            status="pending",
            provider_payment_id="payment-123",
            amount=order.total,
        )
        post_json.return_value = {
            "paymentID": "payment-123",
            "transactionStatus": "Completed",
            "merchantInvoiceNumber": order.order_number,
            "currency": "BDT",
            "amount": str(order.total),
            "trxId": "trx-123",
        }

        self.authenticate(self.member)
        response = self.client.post(
            "/api/payments/bkash/complete/",
            {"order_number": order.order_number, "paymentID": attempt.provider_payment_id},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.status, "confirmed")
        self.assertEqual(attempt.provider_transaction_id, "trx-123")

        order.payment_status = "pending"
        order.save(update_fields=["payment_status"])
        post_json.return_value["amount"] = "1"
        response = self.client.post(
            "/api/payments/bkash/complete/",
            {"order_number": order.order_number, "paymentID": attempt.provider_payment_id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "pending")

    def test_paid_orders_and_payment_attempts_are_visible_in_django_admin(self):
        created = self.create_member_order()
        order = Order.objects.get(order_number=created.data["order_number"])
        attempt = PaymentAttempt.objects.create(
            order=order,
            provider="bkash",
            status="pending",
            provider_payment_id="admin-payment-123",
            amount=order.total,
        )
        admin_user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="admin-password-123",
        )
        self.client.force_login(admin_user)

        orders = self.client.get("/admin/store/order/")
        attempts = self.client.get("/admin/store/paymentattempt/")
        order_detail = self.client.get(f"/admin/store/order/{order.pk}/change/")

        self.assertEqual(orders.status_code, 200)
        self.assertEqual(attempts.status_code, 200)
        self.assertEqual(order_detail.status_code, 200)
        self.assertContains(attempts, "admin-payment-123")
        self.assertContains(order_detail, attempt.provider_payment_id)

    def test_guest_cod_order_remains_supported_but_client_totals_are_ignored(self):
        payload = self.order_payload(payment_method="Cash on Delivery")
        response = self.client.post(self.order_url, payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(order_number=response.data["order_number"])
        self.assertIsNone(order.user)
        self.assertEqual(order.payment_status, "unpaid")
        self.assertEqual(order.total, 1700)
