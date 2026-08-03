import os
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import PERMISSION_CHOICES, Organization, Role, User


class AuthRbacTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org", slug="org")
        self.admin_role = Role.objects.create(
            organization=self.org,
            name="admin",
            permissions=["user.manage", "camera.view"],
            is_system=True,
        )
        self.viewer_role = Role.objects.create(
            organization=self.org, name="viewer", permissions=["camera.view"]
        )
        self.admin = User.objects.create_user(
            username="a", password="pw12345678", organization=self.org, role=self.admin_role
        )
        self.viewer = User.objects.create_user(
            username="v", password="pw12345678", organization=self.org, role=self.viewer_role
        )

    def _login(self, username):
        res = self.client.post(
            "/api/auth/token/", {"username": username, "password": "pw12345678"}, format="json"
        )
        self.assertEqual(res.status_code, 200, res.content)
        return res.data["access"]

    def test_login_returns_user_and_permissions(self):
        res = self.client.post(
            "/api/auth/token/", {"username": "a", "password": "pw12345678"}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("user", res.data)
        self.assertIn("user.manage", res.data["user"]["permissions"])
        self.assertIn("features", res.data["user"])

    @override_settings(FEATURE_FLAGS={"analytics": True, "maps": False})
    def test_login_returns_server_feature_availability(self):
        res = self.client.post(
            "/api/auth/token/", {"username": "a", "password": "pw12345678"}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["user"]["features"], {"analytics": True, "maps": False})

    def test_me_endpoint(self):
        token = self._login("v")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["username"], "v")
        self.assertEqual(res.data["permissions"], ["camera.view"])

    def test_viewer_cannot_manage_users(self):
        token = self._login("v")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = self.client.get("/api/users/")
        self.assertEqual(res.status_code, 403)

    def test_admin_can_list_users(self):
        token = self._login("a")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = self.client.get("/api/users/")
        self.assertEqual(res.status_code, 200)


class BootstrapAdminCommandTests(TestCase):
    @mock.patch.dict(
        os.environ,
        {"DJANGO_SUPERUSER_PASSWORD": "A-strong-bootstrap-password-2026!"},
        clear=False,
    )
    def test_creates_real_admin_without_demo_camera(self):
        call_command(
            "bootstrap_admin",
            username="first-admin",
            email="admin@example.test",
            organization="Operations",
            organization_slug="operations",
            noinput=True,
            verbosity=0,
        )
        user = User.objects.get(username="first-admin")
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.organization.slug, "operations")
        self.assertEqual(user.role.permissions, [code for code, _ in PERMISSION_CHOICES])
        self.assertFalse(user.organization.cameras.exists())
