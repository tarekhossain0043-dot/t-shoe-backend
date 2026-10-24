from rest_framework.test import APITestCase
from django.core.cache import cache


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
