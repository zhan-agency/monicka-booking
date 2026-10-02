from urllib.parse import urljoin

import requests
from django.conf import settings


class MonickaAPIError(Exception):
    def __init__(self, status_code=None):
        self.status_code = status_code
        super().__init__("The booking service is temporarily unavailable.")


class MonickaAPIClient:
    def __init__(self, config, *, session=None, api_key=None):
        self.config = config
        self.session = session or requests.Session()
        self.api_key = api_key if api_key is not None else getattr(settings, "MONICKA_API_KEY", "")

    @property
    def configured(self):
        return bool(self.api_key and self.config.primary_clinic_id)

    def _request(self, method, path, **kwargs):
        if not self.configured:
            raise MonickaAPIError()
        base = self.config.api_base_url.rstrip("/") + "/"
        try:
            response = self.session.request(method, urljoin(base, path.lstrip("/")),
                headers={"X-Clinic-API-Key": self.api_key, "Accept": "application/json"},
                timeout=(3.05, 15), **kwargs)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            raise MonickaAPIError(status) from None

    def catalog(self):
        data = self._request("GET", "/api/plugin/catalog/")
        if data.get("home_clinic_id") != self.config.primary_clinic_id:
            raise MonickaAPIError()
        return data

    def availability(self, *, clinic, therapist, start, end):
        return self._request("GET", "/api/plugin/availability/", params={
            "clinic": clinic, "therapist": therapist, "start": start, "end": end})

    def slots(self, *, clinic, therapist, date):
        return self._request("GET", "/api/slots/", params={
            "clinic": clinic, "therapist": therapist, "date": date})

    def book(self, payload):
        return self._request("POST", "/api/bookings/", json=payload)

    def confirmation(self, code):
        return self._request("GET", f"/api/plugin/confirmation/{code}/")

    def assessment_assignments(self, *, code, phone):
        return self._request("POST", "/api/plugin/assessments/", json={"code": code, "phone": phone})

    def assessment_questionnaire(self, *, code, phone, assessment_type):
        return self._request("POST", f"/api/plugin/assessments/{assessment_type}/form/",
            json={"code": code, "phone": phone})

    def submit_assessment(self, *, code, phone, assessment_type, answers):
        return self._request("POST", f"/api/plugin/assessments/{assessment_type}/",
            json={"action": "submit", "code": code, "phone": phone, "answers": answers})
