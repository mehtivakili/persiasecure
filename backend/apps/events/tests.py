from unittest import mock

from django.db import connection
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, Role, User
from apps.cameras import crypto
from apps.cameras.models import Camera
from apps.events.models import Event, EventComment, NotificationSettings
from apps.mediactl import client as media_client
from apps.recordings.models import EventClip


class InvestigationApiTests(APITestCase):
    def setUp(self):
        # Creating events fires the recordings clip signal; keep it hermetic.
        patcher = mock.patch.object(media_client, "sync_camera_path", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.org = Organization.objects.create(name="O", slug="o")
        role = Role.objects.create(
            organization=self.org, name="op", permissions=["event.view", "event.ack"]
        )
        self.user = User.objects.create_user(
            username="op", password="pw12345678", organization=self.org, role=role
        )
        self.cam = Camera.objects.create(organization=self.org, name="c")
        res = self.client.post(
            "/api/auth/token/", {"username": "op", "password": "pw12345678"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def _event(self, etype="motion"):
        return Event.objects.create(organization=self.org, camera=self.cam, type=etype)

    def test_assign_and_unassign(self):
        ev = self._event()
        r = self.client.post(f"/api/events/{ev.id}/assign/", {"user": self.user.id}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["assigned_to"], self.user.id)
        r = self.client.post(f"/api/events/{ev.id}/assign/", {"user": None}, format="json")
        self.assertIsNone(r.data["assigned_to"])

    def test_assign_rejects_other_org_user(self):
        other = Organization.objects.create(name="O2", slug="o2")
        stranger = User.objects.create_user(username="x", password="pw12345678", organization=other)
        ev = self._event()
        r = self.client.post(f"/api/events/{ev.id}/assign/", {"user": stranger.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_comment_add_and_list(self):
        ev = self._event()
        r = self.client.post(f"/api/events/{ev.id}/comments/", {"text": "checked footage"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.get(f"/api/events/{ev.id}/comments/")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["text"], "checked footage")
        self.assertEqual(EventComment.objects.filter(event=ev).count(), 1)

    def test_related_events_same_camera(self):
        a = self._event("motion")
        b = self._event("tripwire")
        r = self.client.get(f"/api/events/{a.id}/related/")
        self.assertEqual(r.status_code, 200)
        ids = [e["id"] for e in r.data]
        self.assertIn(b.id, ids)
        self.assertNotIn(a.id, ids)

    def test_audit_trail_for_event(self):
        ev = self._event()
        self.client.post(f"/api/events/{ev.id}/acknowledge/")
        r = self.client.get(f"/api/events/{ev.id}/audit/")
        self.assertEqual(r.status_code, 200)
        actions = [a["action"] for a in r.data]
        self.assertIn("event.ack", actions)

    def test_filter_has_clip(self):
        with_clip = self._event("motion")
        EventClip.objects.create(
            event=with_clip, camera=self.cam, start=timezone.now(), end=timezone.now(),
            status="ready",
        )
        self._event("smoke")  # no clip
        r = self.client.get("/api/events/?has_clip=true")
        ids = [e["id"] for e in r.data["results"]]
        self.assertEqual(ids, [with_clip.id])

    def test_free_text_filter(self):
        self._event("motion")
        self._event("smoke")
        r = self.client.get("/api/events/?q=smoke")
        types = {e["type"] for e in r.data["results"]}
        self.assertEqual(types, {"smoke"})


class BookmarkTenancyTests(APITestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="O1", slug="o1")
        self.org2 = Organization.objects.create(name="O2", slug="o2")
        role = Role.objects.create(
            organization=self.org1, name="op", permissions=["playback.view"]
        )
        User.objects.create_user(
            username="op", password="pw12345678", organization=self.org1, role=role
        )
        self.other_cam = Camera.objects.create(organization=self.org2, name="theirs")
        res = self.client.post(
            "/api/auth/token/", {"username": "op", "password": "pw12345678"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_cannot_bookmark_other_org_camera(self):
        r = self.client.post(
            "/api/bookmarks/",
            {"camera": self.other_cam.id, "start": timezone.now().isoformat(), "note": "x"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)


class NotificationCredentialEncryptionTests(TestCase):
    def test_provider_secrets_encrypted_at_rest(self):
        org = Organization.objects.create(name="O", slug="o")
        NotificationSettings.objects.create(
            organization=org, kavenegar_api_key="k-secret", twilio_token="t-secret"
        )
        with connection.cursor() as cur:
            cur.execute(
                "SELECT kavenegar_api_key, twilio_token FROM events_notificationsettings"
            )
            api_key, token = cur.fetchone()
        self.assertTrue(api_key.startswith(crypto.PREFIX))
        self.assertTrue(token.startswith(crypto.PREFIX))
        self.assertNotIn("secret", api_key)
        ns = NotificationSettings.objects.get(organization=org)
        self.assertEqual(ns.kavenegar_api_key, "k-secret")
        self.assertEqual(ns.twilio_token, "t-secret")
