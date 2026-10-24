from unittest.mock import patch

from django.core import signing
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
    def _catalog(self):
        return {"home_clinic_id": 1,
            "branches": [{"id": 1, "name": "شعبه مرکزی"}, {"id": 2, "name": "شعبه غرب"}],
            "therapists": [{"id": 8, "full_name": "دکتر نمونه", "branches": [
                {"clinic_id": 1, "clinic_name": "شعبه مرکزی", "allowed_durations": [45, 60]},
                {"clinic_id": 2, "clinic_name": "شعبه غرب", "allowed_durations": [60]},
            ]}, {"id": 9, "full_name": "دکتر دیگر", "branches": [
                {"clinic_id": 2, "clinic_name": "شعبه غرب", "allowed_durations": [60]},
            ]}]}

    def test_catalog_is_rendered_in_persian_rtl_and_key_is_not_exposed(self):
        config = BookingWidgetConfig.objects.create(primary_clinic_id=1)
        catalog = {"branches": [], "therapists": [{"id": 1, "full_name": "دکتر نمونه", "branches": []}]}
        with patch("monicka_booking.views._client", return_value=(config, type("API", (), {"catalog": lambda self: catalog})())):
            response = self.client.get(reverse("monicka_booking:booking"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="fa" dir="rtl"')
        self.assertIn("دکتر نمونه", response.context["catalog"]["therapists"][0]["full_name"])
        self.assertNotContains(response, "MONICKA_API_KEY")
        self.assertNotContains(response, "city-filter")
        self.assertNotContains(response, "branch-filter")

    def test_multiple_branches_render_a_branch_filter_and_not_a_city_filter(self):
        config = BookingWidgetConfig.objects.create(primary_clinic_id=1)
        catalog = {"branches": [{"id": 1, "name": "شعبه مرکزی"}, {"id": 2, "name": "شعبه غرب"}],
            "therapists": [{"id": 1, "full_name": "دکتر نمونه", "specialties": [], "branches": [
                {"clinic_id": 1, "clinic_name": "شعبه مرکزی", "allowed_durations": [60]},
                {"clinic_id": 2, "clinic_name": "شعبه غرب", "allowed_durations": [60]},
            ]}]}
        api = type("API", (), {"catalog": lambda self: catalog})()
        with patch("monicka_booking.views._client", return_value=(config, api)):
            response = self.client.get(reverse("monicka_booking:booking"))
        self.assertContains(response, 'id="branch-filter"')
        self.assertContains(response, "شعبه مرکزی")
        self.assertContains(response, "شعبه غرب")
        self.assertNotContains(response, "city-filter")

    def test_catalog_failure_shows_friendly_unavailable_state(self):
        config = BookingWidgetConfig.objects.create(primary_clinic_id=1)
        api = type("API", (), {"catalog": lambda self: (_ for _ in ()).throw(MonickaAPIError())})()
        with patch("monicka_booking.views._client", return_value=(config, api)):
            response = self.client.get(reverse("monicka_booking:booking"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "فهرست درمانگران")

    def test_deep_link_locks_page_to_the_selected_therapist_and_branch(self):
        config = BookingWidgetConfig.objects.create(primary_clinic_id=1)
        catalog = self._catalog()
        api = type("API", (), {})()
        api.catalog = lambda: catalog
        with patch("monicka_booking.views._client", return_value=(config, api)):
            response = self.client.get(reverse("monicka_booking:booking"), {"therapist": "8", "clinic": "2"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["special_mode"])
        self.assertEqual(response.context["special_scope"], {"therapist_id": 8, "clinic_id": 2})
        self.assertEqual([row["id"] for row in response.context["catalog"]["therapists"]], [8])
        self.assertEqual([row["clinic_id"] for row in response.context["catalog"]["therapists"][0]["branches"]], [2])
        self.assertContains(response, 'id="step-calendar"')
        self.assertContains(response, 'name="booking_scope"')
        self.assertNotContains(response, "تغییر درمانگر")
        self.assertNotContains(response, "دکتر دیگر")
        self.assertNotContains(response, "شعبه مرکزی")

    def test_deep_link_rejects_missing_or_unrelated_therapist_branch_pairs(self):
        config = BookingWidgetConfig.objects.create(primary_clinic_id=1)
        catalog = self._catalog()
        api = type("API", (), {})()
        api.catalog = lambda: catalog
        with patch("monicka_booking.views._client", return_value=(config, api)):
            missing = self.client.get(reverse("monicka_booking:booking"), {"therapist": "8"})
            unrelated = self.client.get(reverse("monicka_booking:booking"), {"therapist": "9", "clinic": "1"})
        self.assertTrue(missing.context["invalid_scope"])
        self.assertTrue(unrelated.context["invalid_scope"])
        self.assertContains(unrelated, "پیوند رزرو معتبر نیست")
        self.assertNotContains(unrelated, "دکتر نمونه")

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

    def test_deep_link_scope_prevents_changing_therapist_or_branch_at_submit(self):
        token = signing.dumps({"therapist_id": 8, "clinic_id": 2}, salt="monicka-booking-scope")
        with patch("monicka_booking.views._client") as client_factory:
            response = self.client.post(reverse("monicka_booking:submit"), {
                "booking_scope": token, "clinic": "1", "therapist": "8",
                "patient_name": "مراجع", "patient_phone": "09120000000",
                "duration_minutes": "60", "starts_at": "2026-10-04T10:00:00+03:30",
            })
        self.assertEqual(response.status_code, 400)
        client_factory.assert_not_called()

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
        self.assertContains(response, "https://www.monicka.ir/")
        self.assertContains(response, "monicka_booking/monicka-logo.png")
        self.assertContains(response, "توانمند از")


class AssessmentPluginFlowTests(TestCase):
    def setUp(self):
        self.config = BookingWidgetConfig.objects.create(primary_clinic_id=1)

    def test_assessment_client_sends_phone_only_in_post_body(self):
        client = MonickaAPIClient(self.config, api_key="secret", session=type("Session", (), {
            "request": lambda self, method, url, **kwargs: type("Response", (), {
                "raise_for_status": lambda self: None,
                "json": lambda self: {"assessments": []},
            })(),
        })())
        with patch.object(client.session, "request", wraps=client.session.request) as request:
            client.assessment_assignments(code="AB12CD34EF", phone="09123456789")
        self.assertEqual(request.call_args.args[0], "POST")
        self.assertNotIn("phone", request.call_args.args[1])
        self.assertNotIn("params", request.call_args.kwargs)
        self.assertEqual(request.call_args.kwargs["json"], {
            "code": "AB12CD34EF", "phone": "09123456789",
        })

    def test_assessment_access_and_assigned_list_keep_private_values_out_of_urls(self):
        with patch("monicka_booking.views._client", return_value=(self.config, object())):
            access = self.client.get(reverse("monicka_booking:assessments-access"))
        self.assertEqual(access.status_code, 200)
        self.assertContains(access, 'name="confirmation_code"')
        self.assertContains(access, 'name="phone"')

        class API:
            def assessment_assignments(self, *, code, phone):
                self.received = (code, phone)
                return {"assessments": [{"type": "mbti", "title": "آزمون MBTI", "question_count": 60}]}
        api = API()
        with patch("monicka_booking.views._client", return_value=(self.config, api)):
            response = self.client.post(reverse("monicka_booking:assessments-list"), {
                "confirmation_code": "ab12cd34ef", "phone": "09123456789"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(api.received, ("AB12CD34EF", "09123456789"))
        self.assertContains(response, "آزمون MBTI")
        self.assertContains(response, 'name="phone" value="09123456789"')
        self.assertNotIn("09123456789", response.request["PATH_INFO"])

    def test_unverified_assigned_assessments_are_explicitly_shown_for_clinic_followup(self):
        class API:
            def assessment_assignments(self, *, code, phone):
                return {"assessments": [], "unavailable_assessments": [
                    {"type": "bai", "title": "شاخص اضطراب بک"},
                ]}
        with patch("monicka_booking.views._client", return_value=(self.config, API())):
            response = self.client.post(reverse("monicka_booking:assessments-list"), {
                "confirmation_code": "AB12CD34EF", "phone": "09123456789"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نیازمند پیگیری کلینیک")
        self.assertContains(response, "شاخص اضطراب بک")
        self.assertContains(response, "امکان تکمیل آنلاین ندارند")

    def test_questionnaire_is_server_fetched_and_submission_posts_complete_answers(self):
        class API:
            submitted = None
            def assessment_questionnaire(self, *, code, phone, assessment_type):
                self.loaded = (code, phone, assessment_type)
                return {"type": assessment_type, "title": "آزمون نمونه", "question_count": 2,
                    "questions": [
                        {"number": 1, "text": "پرسش یک", "choices": [{"value": 0, "label": "خیر"}, {"value": 1, "label": "بله"}]},
                        {"number": 2, "text": "پرسش دو", "choices": [{"value": 0, "label": "خیر"}, {"value": 1, "label": "بله"}]},
                    ]}
            def submit_assessment(self, **payload):
                self.submitted = payload
                return {"status": "completed"}
        api = API()
        with patch("monicka_booking.views._client", return_value=(self.config, api)):
            form = self.client.post(reverse("monicka_booking:assessment-form", args=["mbti"]), {
                "confirmation_code": "AB12CD34EF", "phone": "09123456789"})
            self.assertEqual(form.status_code, 200)
            self.assertContains(form, 'id="assessment-prev"')
            self.assertContains(form, 'aria-live="polite"')
            self.assertContains(form, "پرسش دو")
            done = self.client.post(reverse("monicka_booking:assessment-submit", args=["mbti"]), {
                "confirmation_code": "AB12CD34EF", "phone": "09123456789",
                "question_count": "2", "q1": "1", "q2": "0"})
        self.assertEqual(done.status_code, 200)
        self.assertEqual(api.loaded, ("AB12CD34EF", "09123456789", "mbti"))
        self.assertEqual(api.submitted, {"code": "AB12CD34EF", "phone": "09123456789",
            "assessment_type": "mbti", "answers": [1, 0]})
        self.assertContains(done, "با موفقیت ثبت شد")

    def test_missing_assessment_answers_never_submit(self):
        class API:
            def submit_assessment(self, **payload):
                raise AssertionError("Incomplete questionnaire must be rejected locally")
        with patch("monicka_booking.views._client", return_value=(self.config, API())):
            response = self.client.post(reverse("monicka_booking:assessment-submit", args=["mbti"]), {
                "confirmation_code": "AB12CD34EF", "phone": "09123456789", "question_count": "2", "q1": "0"})
        self.assertEqual(response.status_code, 400)
