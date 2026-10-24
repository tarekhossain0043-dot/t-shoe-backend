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

    def test_guest_cod_order_remains_supported_but_client_totals_are_ignored(self):
        payload = self.order_payload(payment_method="Cash on Delivery")
        response = self.client.post(self.order_url, payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(order_number=response.data["order_number"])
        self.assertIsNone(order.user)
        self.assertEqual(order.payment_status, "unpaid")
        self.assertEqual(order.total, 1700)
