"""Regression tests for the website plugin's availability and payment handoff."""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from monicka_booking.models import BookingWidgetConfig
from monicka_booking.client import MonickaAPIError


class PluginAvailabilityQualityTests(TestCase):
    def setUp(self):
        self.config = BookingWidgetConfig.objects.create(primary_clinic_id=5)

    def test_slots_proxy_preserves_every_time_duration_and_room_from_api(self):
        expected = [
            {"start": "2026-10-03T10:10:00+03:30", "end": "2026-10-03T10:40:00+03:30",
             "duration_minutes": 30, "available_rooms": [{"id": 1, "capacity": 1}]},
            {"start": "2026-10-03T10:10:00+03:30", "end": "2026-10-03T11:10:00+03:30",
             "duration_minutes": 60, "available_rooms": [{"id": 1, "capacity": 1}, {"id": 2, "capacity": 4}]},
            {"start": "2026-10-03T11:10:00+03:30", "end": "2026-10-03T12:10:00+03:30",
             "duration_minutes": 60, "available_rooms": [{"id": 2, "capacity": 4}]},
        ]
        class API:
            def slots(self, **kwargs):
                self.query = kwargs
                return expected
        api = API()
        with patch("monicka_booking.views._client", return_value=(self.config, api)):
            response = self.client.get(reverse("monicka_booking:slots"), {
                "clinic": "5", "therapist": "22", "date": "1405/07/11",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slots"], expected)
        self.assertEqual(api.query, {"clinic": "5", "therapist": "22", "date": "1405/07/11"})

    def test_availability_proxy_preserves_all_available_days_and_duration_choices(self):
        expected = {"available_days": [
            {"date": "1405/07/11", "durations": [30, 60]},
            {"date": "1405/07/13", "durations": [45]},
        ]}
        class API:
            def availability(self, **kwargs):
                self.query = kwargs
                return expected
        api = API()
        with patch("monicka_booking.views._client", return_value=(self.config, api)):
            response = self.client.get(reverse("monicka_booking:availability"), {
                "clinic": "5", "therapist": "22", "start": "1405/07/11", "end": "1405/07/30",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        self.assertEqual(api.query, {"clinic": "5", "therapist": "22", "start": "1405/07/11", "end": "1405/07/30"})

    def test_api_unavailability_is_a_friendly_retryable_response(self):
        api = type("API", (), {"slots": lambda *args, **kwargs: (_ for _ in ()).throw(MonickaAPIError())})()
        with patch("monicka_booking.views._client", return_value=(self.config, api)):
            response = self.client.get(reverse("monicka_booking:slots"), {
                "clinic": "5", "therapist": "22", "date": "1405/07/11",
            })
        self.assertEqual(response.status_code, 503)
        self.assertIn("سرویس رزرو موقتاً در دسترس نیست", response.json()["error"])


class PluginPaymentHandoffQualityTests(TestCase):
    def setUp(self):
        self.config = BookingWidgetConfig.objects.create(primary_clinic_id=5)
        self.form_data = {
            "clinic": "6", "therapist": "22", "patient_name": "مریم نمونه",
            "patient_phone": "09123456789", "duration_minutes": "60",
            "starts_at": "2026-10-03T10:10:00+03:30", "session_type": "in_person",
            "idempotency_key": "9c52ced7-df94-4d1d-995d-2f5c03543475",
        }

    def test_successful_booking_handoff_posts_once_to_gateway_with_returnable_confirmation(self):
        class API:
            payload = None
            def book(self, payload):
                self.payload = payload
                return {"confirmation_code": "A1B2C3D4E5", "gateway": {
                    "url": "https://gateway.example/pay", "method": "post",
                    "params": {"token": "gateway-token", "amount": "800000"},
                }}
        api = API()
        with patch("monicka_booking.views._client", return_value=(self.config, api)):
            response = self.client.post(reverse("monicka_booking:submit"), {
                **self.form_data, "participant_name": ["همراه"], "participant_phone": ["09121111111"],
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(api.payload["clinic"], 6)
        self.assertEqual(api.payload["therapist"], 22)
        self.assertEqual(api.payload["participant_contacts"], [{
            "patient_name": "همراه", "patient_phone": "09121111111",
        }])
        self.assertEqual(api.payload["return_url"], "http://testserver/booking/complete/")
        self.assertContains(response, 'action="https://gateway.example/pay"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, 'name="token" value="gateway-token"')
        self.assertContains(response, "A1B2C3D4E5")

    def test_retry_or_double_submit_reuses_same_idempotency_key(self):
        class API:
            calls = []
            def book(self, payload):
                self.calls.append(payload)
                return {"confirmation_code": "A1B2C3D4E5", "gateway": {"url": "https://gateway.example/pay"}}
        api = API()
        with patch("monicka_booking.views._client", return_value=(self.config, api)):
            first = self.client.post(reverse("monicka_booking:submit"), self.form_data)
            second = self.client.post(reverse("monicka_booking:submit"), self.form_data)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(api.calls), 2)
        self.assertEqual(api.calls[0]["idempotency_key"], api.calls[1]["idempotency_key"])

    def test_payment_return_without_gateway_handoff_still_uses_confirmation_code(self):
        class API:
            def book(self, payload):
                return {"confirmation_code": "A1B2C3D4E5", "status": "awaiting_payment"}
        with patch("monicka_booking.views._client", return_value=(self.config, API())):
            response = self.client.post(reverse("monicka_booking:submit"), self.form_data)
        self.assertRedirects(response, "/booking/complete/?confirmation=A1B2C3D4E5", fetch_redirect_response=False)

    def test_complete_page_shows_the_server_verified_payment_state(self):
        class API:
            def confirmation(self, code):
                self.code = code
                return {"confirmation_code": code, "status": "paid", "payment_status": "paid",
                    "clinic": "شعبه غرب", "therapist": "درمانگر نمونه"}
        api = API()
        with patch("monicka_booking.views._client", return_value=(self.config, api)):
            response = self.client.get(reverse("monicka_booking:complete"), {"confirmation": "a1b2c3d4e5"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(api.code, "A1B2C3D4E5")
        self.assertContains(response, "پرداخت و رزرو شما ثبت شد")
        self.assertContains(response, "شعبه غرب")

    def test_failed_api_booking_does_not_redirect_to_a_false_success_page(self):
        class API:
            def book(self, payload):
                raise MonickaAPIError(status_code=400)
        with patch("monicka_booking.views._client", return_value=(self.config, API())):
            response = self.client.post(reverse("monicka_booking:submit"), self.form_data)
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "تکمیل درخواست ممکن نشد", status_code=503)
