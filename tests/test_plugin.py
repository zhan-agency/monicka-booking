from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from monicka_booking.client import MonickaAPIClient, MonickaAPIError
from monicka_booking.models import BookingWidgetConfig


class BookingConfigTests(TestCase):
    def test_singleton_is_fixed_to_primary_key_one(self):
        config = BookingWidgetConfig.objects.create(primary_clinic_id=12)
        self.assertEqual(config.pk, 1)
        self.assertEqual(BookingWidgetConfig.get_solo().primary_clinic_id, 12)

    def test_api_origin_requires_https_outside_local_development(self):
        config = BookingWidgetConfig(api_base_url="http://api.example.test")
        with self.assertRaises(Exception):
            config.full_clean()
        with self.assertRaises(Exception):
            BookingWidgetConfig(api_base_url="https://api.example.test/unexpected-path").full_clean()

    @override_settings(MONICKA_API_KEY="secret-never-rendered")
    def test_client_keeps_key_in_server_side_request_header(self):
        config = BookingWidgetConfig(primary_clinic_id=1)
        client = MonickaAPIClient(config)
        self.assertTrue(client.configured)
        with patch.object(client.session, "request") as request:
            request.return_value.raise_for_status.return_value = None
            request.return_value.json.return_value = {"home_clinic_id": 1, "therapists": []}
            client.catalog()
        self.assertEqual(request.call_args.kwargs["headers"]["X-Clinic-API-Key"], "secret-never-rendered")

    def test_unconfigured_client_does_not_make_network_request(self):
        with patch("monicka_booking.client.requests.Session.request") as request:
            with self.assertRaises(MonickaAPIError):
                MonickaAPIClient(BookingWidgetConfig()).catalog()
        request.assert_not_called()


class BookingPageTests(TestCase):
    def test_catalog_is_rendered_in_persian_rtl_and_key_is_not_exposed(self):
        config = BookingWidgetConfig.objects.create(primary_clinic_id=1)
        catalog = {"branches": [], "therapists": [{"id": 1, "full_name": "دکتر نمونه", "branches": []}]}
        with patch("monicka_booking.views._client", return_value=(config, type("API", (), {"catalog": lambda self: catalog})())):
            response = self.client.get(reverse("monicka_booking:booking"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="fa" dir="rtl"')
        self.assertIn("دکتر نمونه", response.context["catalog"]["therapists"][0]["full_name"])
        self.assertNotContains(response, "MONICKA_API_KEY")

    def test_catalog_failure_shows_friendly_unavailable_state(self):
        config = BookingWidgetConfig.objects.create(primary_clinic_id=1)
        api = type("API", (), {"catalog": lambda self: (_ for _ in ()).throw(MonickaAPIError())})()
        with patch("monicka_booking.views._client", return_value=(config, api)):
            response = self.client.get(reverse("monicka_booking:booking"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "فهرست درمانگران")

    def test_completion_requires_a_confirmation_code(self):
        response = self.client.get(reverse("monicka_booking:complete"))
        self.assertEqual(response.status_code, 400)

    def test_booking_submission_posts_server_side_with_idempotency_and_return_url(self):
        config = BookingWidgetConfig.objects.create(primary_clinic_id=1)
        class API:
            payload = None
            def book(self, payload):
                self.payload = payload
                return {"confirmation_code": "AB12CD34EF", "gateway": {
                    "url": "https://bank.example/pay", "method": "post", "params": {"token": "opaque"}}}
        api = API()
        with patch("monicka_booking.views._client", return_value=(config, api)):
            response = self.client.post(reverse("monicka_booking:submit"), {
                "clinic": "3", "therapist": "8", "patient_name": "Patient", "patient_phone": "09120000000",
                "duration_minutes": "60", "starts_at": "2026-10-04T10:00:00+03:30",
                "idempotency_key": "00000000-0000-0000-0000-000000000001", "session_type": "online",
                "participant_name": ["Guest"], "participant_phone": ["09121111111"],
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(api.payload["session_type"], "online")
        self.assertEqual(len(api.payload["participant_contacts"]), 1)
        self.assertEqual(api.payload["idempotency_key"], "00000000-0000-0000-0000-000000000001")
        self.assertEqual(api.payload["return_url"], "http://testserver/booking/complete/")
        self.assertContains(response, "https://bank.example/pay")

    def test_completion_verifies_code_through_api_before_rendering_status(self):
        config = BookingWidgetConfig.objects.create(primary_clinic_id=1)
        booking = {"confirmation_code": "AB12CD34EF", "status": "paid", "clinic": "Central",
            "therapist": "Dr Example", "payment_status": "success"}
        class API:
            def confirmation(self, code):
                self.code = code
                return booking
        api = API()
        with patch("monicka_booking.views._client", return_value=(config, api)):
            response = self.client.get(reverse("monicka_booking:complete"), {"confirmation": "ab12cd34ef"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(api.code, "AB12CD34EF")
        self.assertContains(response, "AB12CD34EF")
